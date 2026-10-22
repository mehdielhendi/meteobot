from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.config import Settings
from app.models import ForecastDay, WeatherObservation

# WMO weather interpretation codes (subset)
WMO_CODES: dict[int, str] = {
    0: "ciel dégagé",
    1: "principalement dégagé",
    2: "partiellement nuageux",
    3: "couvert",
    45: "brouillard",
    48: "brouillard givrant",
    51: "bruine légère",
    61: "pluie faible",
    63: "pluie modérée",
    65: "pluie forte",
    71: "neige faible",
    80: "averses",
    95: "orage",
}


class WeatherService:
    """Fetches observations and forecasts (Open-Meteo by default)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._geocode_cache: dict[str, tuple[float, float, str]] = {}

    async def resolve_location(self, city: str) -> tuple[float, float, str]:
        key = city.strip().lower()
        if key in self._geocode_cache:
            return self._geocode_cache[key]

        if key == self.settings.default_city.lower():
            result = (
                self.settings.default_lat,
                self.settings.default_lon,
                self.settings.default_city,
            )
            self._geocode_cache[key] = result
            return result

        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": city, "count": 1, "language": "fr", "format": "json"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        results = payload.get("results") or []
        if not results:
            raise ValueError(f"Localité introuvable : {city}")

        place = results[0]
        result = (
            float(place["latitude"]),
            float(place["longitude"]),
            str(place.get("name") or city),
        )
        self._geocode_cache[key] = result
        return result

    async def get_current(self, city: str) -> WeatherObservation:
        lat, lon, resolved = await self.resolve_location(city)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "timezone": "auto",
            "wind_speed_unit": "kmh",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        current = payload["current"]
        code = int(current.get("weather_code") or 0)
        return WeatherObservation(
            city=resolved,
            temperature_c=float(current["temperature_2m"]),
            humidity_pct=_optional_float(current.get("relative_humidity_2m")),
            wind_speed_kmh=_optional_float(current.get("wind_speed_10m")),
            weather_code=code,
            description=WMO_CODES.get(code, "conditions variables"),
            observed_at=datetime.now(timezone.utc),
        )

    async def get_forecast(self, city: str, days: int = 5) -> list[ForecastDay]:
        lat, lon, resolved = await self.resolve_location(city)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
            "forecast_days": max(1, min(days, 7)),
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        daily = payload["daily"]
        dates = daily["time"]
        forecast: list[ForecastDay] = []
        for i, date in enumerate(dates):
            code = int(daily["weather_code"][i])
            forecast.append(
                ForecastDay(
                    date=date,
                    temp_max_c=float(daily["temperature_2m_max"][i]),
                    temp_min_c=float(daily["temperature_2m_min"][i]),
                    precipitation_mm=_optional_float(daily["precipitation_sum"][i]),
                    description=WMO_CODES.get(code, "conditions variables"),
                )
            )
        # Attach resolved city name on first item via description context in chatbot
        _ = resolved
        return forecast

    async def get_alerts(self, city: str) -> dict:
        """Placeholder for national meteorological alert feeds."""
        _, _, resolved = await self.resolve_location(city)
        return {
            "city": resolved,
            "alerts": [],
            "message": (
                "Aucune alerte intégrée pour le moment. "
                "Ce module est prêt pour brancher les bulletins officiels."
            ),
        }

    async def get_climate_summary(self, city: str) -> dict:
        """Simple climate snapshot via recent daily normals proxy."""
        lat, lon, resolved = await self.resolve_location(city)
        url = "https://climate-api.open-meteo.com/v1/climate"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": "1991-01-01",
            "end_date": "2020-12-31",
            "models": "EC_Earth3P_HR",
            "daily": "temperature_2m_mean",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
            values = payload.get("daily", {}).get("temperature_2m_mean") or []
            usable = [float(v) for v in values if v is not None]
            mean = sum(usable) / len(usable) if usable else None
            return {
                "city": resolved,
                "period": "1991-2020",
                "mean_temperature_c": round(mean, 1) if mean is not None else None,
                "note": "Résumé climatologique indicatif (Open-Meteo Climate API).",
            }
        except Exception:
            return {
                "city": resolved,
                "period": "n/a",
                "mean_temperature_c": None,
                "note": (
                    "Service climatologique temporairement indisponible. "
                    "L'intégration des archives nationales pourra être branchée ici."
                ),
            }


def _optional_float(value) -> float | None:
    if value is None:
        return None
    return float(value)
