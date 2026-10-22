"""Region scenario helpers (où risque-t-il de … dans le Nord)."""

from __future__ import annotations

import re
import unicodedata

from app.services.intent import Metric
from app.services.reply_style import styled_reply
from app.services.special_store import FIELD_LABELS, SpecialStore
from app.services.bms_store import BmsStore


def _norm(text: str) -> str:
    folded = unicodedata.normalize("NFD", text.lower())
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


# DRMNO-oriented regional buckets (SPECIAL cities + BMS province aliases)
REGIONS: dict[str, list[str]] = {
    "nord": [
        "Tanger",
        "Tetouan",
        "Larache",
        "Chefchaouen",
        "Al Houceima",
        "Ouazzane",
        "Kenitra",
        "Rabat",
        "Rabat Sale",
        "Temara",
        "Sidi Slimane",
        "Sidi Kacem",
        "Khemisset",
    ],
    "atlantique": [
        "Tanger",
        "Larache",
        "Kenitra",
        "Rabat",
        "Rabat Sale",
        "Temara",
    ],
    "rif": [
        "Al Houceima",
        "Tetouan",
        "Chefchaouen",
        "Ouazzane",
    ],
}


def detect_region(message: str) -> str | None:
    text = _norm(message)
    if any(k in text for k in ("nord", "north", "drmno", "region nord")):
        return "nord"
    if "rif" in text:
        return "rif"
    if "atlantique" in text or "cote" in text or "littoral" in text:
        return "atlantique"
    return None


def is_scenario_query(message: str) -> bool:
    text = message.lower()
    triggers = (
        "où risque",
        "ou risque",
        "où pleut",
        "ou pleut",
        "où va-t-il",
        "ou va-t-il",
        "quelles villes",
        "quelles provinces",
        "dans le nord",
        "sur le nord",
        "zone à risque",
        "zones à risque",
    )
    return any(t in text for t in triggers) or (
        detect_region(message) is not None
        and any(k in text for k in ("pluie", "vent", "alerte", "chaleur", "risque", "orage"))
    )


def scenario_metric(message: str) -> Metric | None:
    text = message.lower()
    if any(k in text for k in ("pluie", "pleuvoir", "averses", "précip", "precip")):
        return Metric.RAIN
    if any(k in text for k in ("vent", "rafale")):
        return Metric.WIND
    if any(k in text for k in ("chaleur", "canicule", "température", "temperature")):
        return Metric.TEXTREMES
    if "ciel" in text:
        return Metric.SKY
    return Metric.RAIN


def run_rain_scenario(
    special: SpecialStore,
    region: str | None,
    day_filter: str | None,
    date: str | None,
    metric: Metric | None,
) -> str:
    region_key = region or "nord"
    cities = REGIONS.get(region_key, REGIONS["nord"])
    metric = metric or Metric.RAIN
    fields = {
        Metric.RAIN: ("rain", "phenomena"),
        Metric.WIND: ("vent",),
        Metric.TEXTREMES: ("textremes", "tmax", "tmin"),
        Metric.SKY: ("sky",),
        Metric.PHENOMENA: ("phenomena",),
    }.get(metric, ("rain", "phenomena"))

    def _is_rain_signal(value: str) -> bool:
        low = value.lower().strip()
        if not low or low in {"néant", "neant", "-", "nil", "aucune", "aucun", "0"}:
            return False
        return True

    hits: list[tuple[str, str, str]] = []
    for city in cities:
        forecast = special.get_forecast(city, date=date)
        if not forecast:
            continue
        periods = special._filter_periods(forecast.get("periods") or [], day_filter)
        for period in periods:
            values = []
            for field in fields:
                value = period.get(field)
                if not value:
                    continue
                if metric == Metric.RAIN and not _is_rain_signal(str(value)):
                    continue
                values.append(f"{FIELD_LABELS.get(field, field)} : {value}")
            if values:
                hits.append((city, period.get("label") or "", " · ".join(values)))
                break

    if not hits:
        return styled_reply(
            title=f"Scénario — région {region_key}",
            meta=[f"Jour : {day_filter or 'tous créneaux'}"],
            body_lines=["Aucun signal notable trouvé dans les bulletins SPECIAL de cette zone."],
            source="SPECIAL régional",
        )

    sections = [
        (f"{city} · {label}", [detail])
        for city, label, detail in hits
    ]
    return styled_reply(
        title=f"Scénario — où surveiller ({region_key})",
        meta=[
            f"Jour : {day_filter or 'tous créneaux'}",
            f"Paramètre : {metric.value}",
            f"Villes balayées : {len(cities)}",
        ],
        sections=sections,
        source="SPECIAL régional DRMNO",
    )


def run_alert_scenario(bms: BmsStore, region: str | None, date: str | None) -> str:
    region_key = region or "nord"
    cities = REGIONS.get(region_key, REGIONS["nord"])
    bulletin = bms.for_date(date)
    if not bulletin:
        return "Aucun bulletin BMS disponible."

    sections: list[tuple[str, list[str]]] = []
    for city in cities:
        hits = bms.find_for_place(city, bulletin.get("issue_date"))
        if not hits:
            continue
        fields = []
        for hit in hits:
            line = f"{hit.get('type')} · vigilance {hit.get('vigilance_level')}"
            if hit.get("intensity"):
                line += f" · {hit['intensity']}"
            fields.append(line)
        sections.append((city, fields))

    if not sections:
        return styled_reply(
            title=f"Scénario alertes — {region_key}",
            meta=[f"Bulletin : {bulletin.get('issue_date')}"],
            body_lines=["Aucune alerte BMS croisée pour les villes de cette zone."],
            source=bulletin.get("source_file"),
        )
    return styled_reply(
        title=f"Scénario alertes — {region_key}",
        meta=[
            f"Bulletin : {bulletin.get('issue_date')}",
            f"NR : {bulletin.get('bulletin_nr')}",
        ],
        sections=sections,
        source=bulletin.get("source_file"),
    )
