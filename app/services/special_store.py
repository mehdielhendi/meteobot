from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from app.services.intent import Metric
from app.services.reply_style import pad_label, styled_reply


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFD", text.lower())
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


# Common spelling variants across OBS / SPECIAL / user input
PLACE_ALIASES = {
    "al hoceima": "al houceima",
    "alhoceima": "al houceima",
    "al hoceïma": "al houceima",
    "ouezzane": "ouazzane",
    "wazzane": "ouazzane",
    "rabat sale": "rabat sale",
    "rabat salé": "rabat sale",
    "mdiq fnideq": "mdiq fnideq",
}


def canonical_place(text: str) -> str:
    needle = normalize(text)
    return PLACE_ALIASES.get(needle, needle)


FIELD_LABELS = {
    "sky": "État du ciel",
    "phenomena": "Phénomènes",
    "vent": "Vent",
    "textremes": "Températures extrêmes",
    "tmin": "Température min",
    "tmax": "Température max",
    "rain": "Pluie (mm)",
}

METRIC_TO_FIELDS = {
    Metric.TEMPERATURE: ("textremes", "tmin", "tmax"),
    Metric.TEXTREMES: ("textremes",),
    Metric.SKY: ("sky",),
    Metric.PHENOMENA: ("phenomena",),
    Metric.TN: ("tmin", "textremes"),
    Metric.TX: ("tmax", "textremes"),
    Metric.WIND: ("vent",),
    Metric.RAIN: ("rain",),
}


class SpecialStore:
    """Local SPECIAL forecast bulletins (prévisions par ville)."""

    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self.forecasts: list[dict] = []
        self.cities: list[str] = []
        self._load()

    def _load(self) -> None:
        if not self.data_path.exists():
            self.forecasts = []
            self.cities = []
            return
        payload = json.loads(self.data_path.read_text(encoding="utf-8"))
        self.forecasts = payload.get("forecasts") or []
        self.cities = payload.get("cities") or []

    @property
    def available(self) -> bool:
        return bool(self.forecasts)

    def list_cities(self) -> list[str]:
        return list(self.cities)

    def match_city(self, query: str) -> str | None:
        needle = canonical_place(query)
        if not needle:
            return None
        best: tuple[float, str] | None = None
        for city in self.cities:
            name = canonical_place(city)
            score = 0.0
            if needle == name:
                score = 100.0
            elif needle in name or name in needle:
                score = 80.0
            else:
                ratio = SequenceMatcher(None, needle, name).ratio()
                if ratio >= 0.88:
                    score = 70.0 + ratio * 10.0
            if score and (best is None or score > best[0]):
                best = (score, city)
        return best[1] if best else None

    def get_forecast(self, place: str, date: str | None = None) -> dict | None:
        city = self.match_city(place)
        if city is None:
            return None
        candidates = [f for f in self.forecasts if normalize(f.get("city") or "") == normalize(city)]
        if not candidates:
            return None
        if date:
            dated = [f for f in candidates if f.get("issue_date") == date]
            if dated:
                return dated[-1]
        return candidates[-1]

    def _filter_periods(self, periods: list[dict], day_filter: str | None) -> list[dict]:
        if not day_filter:
            return periods
        needle = normalize(day_filter)
        filtered = []
        for p in periods:
            label_n = normalize(p.get("label") or "")
            if needle == "demain":
                if "demain" in label_n and "apres demain" not in label_n:
                    filtered.append(p)
            elif needle in label_n:
                filtered.append(p)
        return filtered

    def _wanted_fields(self, metric: Metric | str | None) -> tuple[str, ...] | None:
        if not metric:
            return None
        try:
            metric_enum = metric if isinstance(metric, Metric) else Metric(str(metric))
        except ValueError:
            return None
        return METRIC_TO_FIELDS.get(metric_enum)

    def _period_value(self, period: dict, fields: tuple[str, ...] | None) -> str:
        if fields:
            parts = []
            for field in fields:
                value = period.get(field)
                if value:
                    parts.append(str(value))
            return " · ".join(parts) if parts else "non renseigné"
        parts = []
        for field, label in FIELD_LABELS.items():
            value = period.get(field)
            if value:
                parts.append(f"{label} : {value}")
        return " | ".join(parts) if parts else "non renseigné"

    def format_forecast(
        self,
        forecast: dict,
        metric: Metric | str | None = None,
        day_filter: str | None = None,
    ) -> str:
        wanted_fields = self._wanted_fields(metric)
        periods = self._filter_periods(forecast.get("periods") or [], day_filter)
        sections: list[tuple[str, list[str]]] = []
        for period in periods:
            fields: list[str] = []
            shown = 0
            for field, label in FIELD_LABELS.items():
                if wanted_fields and field not in wanted_fields:
                    continue
                value = period.get(field)
                if value:
                    fields.append(f"{label} : {value}")
                    shown += 1
            if wanted_fields and shown == 0:
                fields.append("(non renseigné pour ce créneau)")
            sections.append((period.get("label") or "Créneau", fields))

        meta = [f"Date du bulletin : {forecast.get('issue_date')}"]
        if forecast.get("issued_label"):
            meta.append(f"Établi : {forecast['issued_label']}")
        return styled_reply(
            title=f"Prévision SPECIAL — {forecast.get('city')} ({forecast.get('horizon_h')}h)",
            meta=meta,
            sections=sections,
            source=forecast.get("source_file"),
        )

    def format_compare(
        self,
        city_a: str,
        city_b: str,
        date: str | None = None,
        metric: Metric | str | None = None,
        day_filter: str | None = None,
    ) -> str | None:
        fa = self.get_forecast(city_a, date=date)
        fb = self.get_forecast(city_b, date=date)
        if fa is None or fb is None:
            return None

        # Prefer matching issue dates when possible
        if fa.get("issue_date") != fb.get("issue_date"):
            common = None
            dates_a = {
                f.get("issue_date")
                for f in self.forecasts
                if normalize(f.get("city") or "") == normalize(fa.get("city") or "")
            }
            dates_b = {
                f.get("issue_date")
                for f in self.forecasts
                if normalize(f.get("city") or "") == normalize(fb.get("city") or "")
            }
            shared = sorted(dates_a & dates_b)
            if shared:
                common = shared[-1]
                fa = self.get_forecast(city_a, date=common) or fa
                fb = self.get_forecast(city_b, date=common) or fb

        pa = {
            p.get("label"): p
            for p in self._filter_periods(fa.get("periods") or [], day_filter)
        }
        pb = {
            p.get("label"): p
            for p in self._filter_periods(fb.get("periods") or [], day_filter)
        }
        labels = list(dict.fromkeys([*pa.keys(), *pb.keys()]))
        if not labels:
            return None

        name_a = fa.get("city") or city_a
        name_b = fb.get("city") or city_b
        width = max(len(name_a), len(name_b), 8)
        sections: list[tuple[str, list[str]]] = []
        for label in labels:
            left = pa.get(label) or {}
            right = pb.get(label) or {}
            if metric is None:
                row_fields: list[str] = []
                for field in ("textremes", "tmin", "tmax", "vent", "sky", "phenomena", "rain"):
                    va = left.get(field)
                    vb = right.get(field)
                    if not va and not vb:
                        continue
                    label_field = FIELD_LABELS.get(field, field)
                    row_fields.append(label_field)
                    row_fields.append(
                        f"{pad_label(name_a, width)} : {va or 'non renseigné'}"
                    )
                    row_fields.append(
                        f"{pad_label(name_b, width)} : {vb or 'non renseigné'}"
                    )
                if row_fields:
                    sections.append((label or "Créneau", row_fields))
            else:
                fields_for_metric = self._wanted_fields(metric)
                va = self._period_value(left, fields_for_metric)
                vb = self._period_value(right, fields_for_metric)
                fields = [
                    f"{pad_label(name_a, width)} : {va}",
                    f"{pad_label(name_b, width)} : {vb}",
                ]
                note = self._compare_note(va, vb, name_a, name_b, metric)
                if note:
                    fields.append(f"Écart : {note}")
                sections.append((label or "Créneau", fields))

        day_meta = day_filter or "tous créneaux"
        return styled_reply(
            title=f"Comparaison SPECIAL — {name_a} × {name_b}",
            meta=[
                f"Jour : {day_meta} · Bulletin : {fa.get('issue_date')}",
            ],
            sections=sections,
            source=f"{fa.get('source_file')} · {fb.get('source_file')}",
        )

    def _compare_note(
        self,
        value_a: str,
        value_b: str,
        name_a: str,
        name_b: str,
        metric: Metric | str | None,
    ) -> str | None:
        if value_a == "non renseigné" or value_b == "non renseigné":
            return None
        key = metric.value if isinstance(metric, Metric) else str(metric or "")
        if key in {"textremes", "temperature", "tn", "tx", "t12"}:
            nums_a = [
                float(x)
                for x in re.findall(r"(\d+(?:[.,]\d+)?)", value_a.replace(",", "."))
            ]
            nums_b = [
                float(x)
                for x in re.findall(r"(\d+(?:[.,]\d+)?)", value_b.replace(",", "."))
            ]
            if nums_a and nums_b:
                avg_a = sum(nums_a) / len(nums_a)
                avg_b = sum(nums_b) / len(nums_b)
                if abs(avg_a - avg_b) < 0.3:
                    return "températures proches"
                if avg_a > avg_b:
                    return f"{name_a} plus chaud"
                return f"{name_b} plus chaud"
        return None

