"""Operational dashboard payload for map pins, ticker, and metric cards."""

from __future__ import annotations

from app.services.bms_store import BmsStore
from app.services.obs_daily_store import DailyObsStore
from app.services.obs_store import ObsStore

DRMNO_MAP_PLACES = [
    "Tanger",
    "Tetouan",
    "Larache",
    "Chefchaouen",
    "Al Hoceima",
    "Ouazzane",
    "Kenitra",
    "Rabat",
    "Temara",
    "Khemisset",
    "Sidi Kacem",
    "Sidi Slimane",
]


def build_dashboard(
    *,
    bms: BmsStore,
    obs: ObsStore,
    daily: DailyObsStore,
) -> dict:
    overview = bms.vigilance_overview(DRMNO_MAP_PLACES) if bms.available else {
        "issue_date": None,
        "bulletin_nr": None,
        "issued_label": None,
        "places": {p: {"level": "vert", "type": None, "active": False} for p in DRMNO_MAP_PLACES},
        "active_count": 0,
        "active_places": [],
        "phenomena": [],
    }

    ticker: list[str] = []
    temps: list[float] = []
    obs_hour = None
    bulletin = obs.latest_bulletin() if obs.available else None
    if bulletin:
        obs_hour = bulletin.get("hour")
        for row in bulletin.get("stations") or []:
            name = row.get("station") or "Station"
            temp = row.get("temperature_c")
            if temp is None:
                continue
            temps.append(float(temp))
            wind = row.get("wind_speed_kt")
            hum = row.get("humidity_pct")
            bits = [f"{name} {temp:.1f}°C"]
            if wind is not None:
                bits.append(f"vent {wind} kt")
            if hum is not None:
                bits.append(f"Hu {hum}%")
            ticker.append(" · ".join(bits))

    if not ticker and daily.available:
        day = daily.bulletin_for_date(None)
        if day:
            for row in day.get("stations") or []:
                name = row.get("station") or "Station"
                tx = row.get("tx_c")
                tn = row.get("tn_c")
                if tx is not None:
                    temps.append(float(tx))
                label = name
                if tn is not None and tx is not None:
                    label = f"{name} TN {tn:.0f}° / TX {tx:.0f}°"
                elif tx is not None:
                    label = f"{name} TX {tx:.0f}°C"
                ticker.append(label)

    avg_temp = round(sum(temps) / len(temps), 1) if temps else None
    phenomena = overview.get("phenomena") or []
    rank = {"vert": 0, "jaune": 1, "orange": 2, "rouge": 3}
    top_level = "vert"
    for info in (overview.get("places") or {}).values():
        lvl = info.get("level") or "vert"
        if rank.get(lvl, 0) > rank.get(top_level, 0):
            top_level = lvl
    if top_level == "vert":
        for ph in phenomena:
            lvl = ph.get("level") or "vert"
            if rank.get(lvl, 0) > rank.get(top_level, 0):
                top_level = lvl

    return {
        "places": overview.get("places") or {},
        "metrics": {
            "avg_temp_c": avg_temp,
            "obs_hour": obs_hour,
            "station_count": len(temps),
            "active_alerts": overview.get("active_count") or 0,
            "active_places": overview.get("active_places") or [],
            "bulletin_nr": overview.get("bulletin_nr"),
            "issue_date": overview.get("issue_date"),
            "top_level": top_level,
            "phenomena": [p.get("type") for p in phenomena if p.get("type")],
        },
        "ticker": ticker
        or [
            "Réseau OBS DRMNO en attente",
            "Bulletins BMS / SPECIAL chargés localement",
        ],
    }
