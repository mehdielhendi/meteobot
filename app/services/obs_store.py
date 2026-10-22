from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.services.intent import Metric
from app.services.reply_style import styled_reply


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFD", text.lower())
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


@dataclass
class ObsHit:
    date: str
    time: str
    datetime: str
    province: str
    station: str
    station_id: str | None
    temperature_c: float | None
    dew_point_c: float | None
    humidity_pct: float | None
    visibility_km: float | None
    pressure_hpa: float | None
    wind: str | None
    rain_mm: float | None
    snow_cm: float | None
    source_file: str

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "time": self.time,
            "datetime": self.datetime,
            "province": self.province,
            "station": self.station,
            "station_id": self.station_id,
            "temperature_c": self.temperature_c,
            "dew_point_c": self.dew_point_c,
            "humidity_pct": self.humidity_pct,
            "visibility_km": self.visibility_km,
            "pressure_hpa": self.pressure_hpa,
            "wind": self.wind,
            "rain_mm": self.rain_mm,
            "snow_cm": self.snow_cm,
            "source_file": self.source_file,
        }


class ObsStore:
    """Local DRMNO hourly observations used as chatbot ground truth."""

    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self.bulletins: list[dict] = []
        self.stations: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.data_path.exists():
            self.bulletins = []
            self.stations = []
            return
        payload = json.loads(self.data_path.read_text(encoding="utf-8"))
        self.bulletins = payload.get("bulletins") or []
        self.stations = payload.get("stations") or []

    @property
    def available(self) -> bool:
        return bool(self.bulletins)

    def list_station_names(self) -> list[str]:
        return sorted({s["station"] for s in self.stations if s.get("station")})

    def match_station(self, query: str) -> dict | None:
        needle = normalize(query)
        if not needle:
            return None

        # Exact / contained station name
        best: tuple[int, dict] | None = None
        for station in self.stations:
            name = normalize(station.get("station") or "")
            province = normalize(station.get("province") or "")
            sid = (station.get("station_id") or "").lower()
            score = 0
            if needle == name or needle == sid:
                score = 100
            elif needle in name or name in needle:
                score = 80
            elif needle in province or province in needle:
                score = 50
            if score and (best is None or score > best[0]):
                best = (score, station)
        return best[1] if best else None

    def latest_bulletin(self) -> dict | None:
        if not self.bulletins:
            return None
        return self.bulletins[-1]

    def bulletin_for_hour(self, hour: int | None) -> dict | None:
        if not self.bulletins:
            return None
        if hour is None:
            return self.latest_bulletin()
        for bulletin in reversed(self.bulletins):
            if bulletin.get("hour") == hour:
                return bulletin
        return None

    def get_observation(
        self,
        place: str,
        hour: int | None = None,
    ) -> ObsHit | None:
        station = self.match_station(place)
        if station is None:
            return None

        bulletin = self.bulletin_for_hour(hour)
        if bulletin is None:
            return None

        target_id = station.get("station_id")
        target_name = normalize(station.get("station") or "")
        for row in bulletin.get("stations") or []:
            same_id = target_id and row.get("station_id") == target_id
            same_name = normalize(row.get("station") or "") == target_name
            if not (same_id or same_name):
                continue
            return ObsHit(
                date=bulletin["date"],
                time=bulletin["time"],
                datetime=bulletin["datetime"],
                province=row.get("province") or "",
                station=row.get("station") or "",
                station_id=row.get("station_id"),
                temperature_c=row.get("temperature_c"),
                dew_point_c=row.get("dew_point_c"),
                humidity_pct=row.get("humidity_pct"),
                visibility_km=row.get("visibility_km"),
                pressure_hpa=row.get("pressure_hpa"),
                wind=row.get("wind"),
                rain_mm=row.get("rain_mm"),
                snow_cm=row.get("snow_cm"),
                source_file=bulletin.get("source_file") or "",
            )
        return None

    def format_observation(self, hit: ObsHit, metric: Metric | str | None = None) -> str:
        """Format OBS reply.

        STRICT FILTERING RULE: if ``metric`` is set (vent, humidité, …),
        return ONLY that parameter with location, date/time, and source.
        General queries keep the full summary.
        """
        metric_lines = {
            "temperature": (
                f"Température : {hit.temperature_c:.1f}°C"
                if hit.temperature_c is not None
                else "Température : non renseignée"
            ),
            "dew_point": (
                f"Point de rosée : {hit.dew_point_c:.1f}°C"
                if hit.dew_point_c is not None
                else "Point de rosée : non renseigné"
            ),
            "humidity": (
                f"Humidité : {hit.humidity_pct:.0f}%"
                if hit.humidity_pct is not None
                else "Humidité : non renseignée"
            ),
            "visibility": (
                f"Visibilité : {hit.visibility_km:.1f} km"
                if hit.visibility_km is not None
                else "Visibilité : non renseignée"
            ),
            "pressure": (
                f"Pression : {hit.pressure_hpa:.1f} hPa"
                if hit.pressure_hpa is not None
                else "Pression : non renseignée"
            ),
            "wind": (
                f"Vent : {hit.wind} kt"
                if hit.wind
                else "Vent : non renseigné"
            ),
            "rain": (
                f"Pluie : {hit.rain_mm:.1f} mm"
                if hit.rain_mm is not None
                else "Pluie : non renseignée"
            ),
            "snow": (
                f"Neige : {hit.snow_cm:.1f} cm"
                if hit.snow_cm is not None
                else "Neige : non renseignée"
            ),
        }

        if metric:
            key = metric.value if hasattr(metric, "value") else str(metric)
            line = metric_lines.get(key)
            if line is None:
                return self.format_observation(hit, metric=None)
            return styled_reply(
                title=f"Observation DRMNO — {hit.station} ({hit.province})",
                meta=[f"Date/heure : {hit.date} à {hit.time}"],
                body_lines=[line],
                source=hit.source_file,
            )

        body = []
        if hit.temperature_c is not None:
            body.append(metric_lines["temperature"])
        if hit.dew_point_c is not None:
            body.append(metric_lines["dew_point"])
        if hit.humidity_pct is not None:
            body.append(metric_lines["humidity"])
        if hit.visibility_km is not None:
            body.append(metric_lines["visibility"])
        if hit.pressure_hpa is not None:
            body.append(metric_lines["pressure"])
        if hit.wind:
            body.append(metric_lines["wind"])
        if hit.rain_mm is not None:
            body.append(metric_lines["rain"])
        if hit.snow_cm is not None:
            body.append(metric_lines["snow"])
        return styled_reply(
            title=f"Observation DRMNO — {hit.station} ({hit.province})",
            meta=[f"Date/heure : {hit.date} à {hit.time}"],
            body_lines=body,
            source=hit.source_file,
        )
