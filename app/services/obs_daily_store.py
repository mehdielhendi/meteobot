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
class DailyObsHit:
    date: str
    province: str
    station: str
    station_id: str | None
    tn_c: float | None
    tx_c: float | None
    t12_c: float | None
    rr06_mm: float | None
    rr12_mm: float | None
    rr18_mm: float | None
    hu06_pct: float | None
    hu12_pct: float | None
    hu18_pct: float | None
    source_file: str

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "province": self.province,
            "station": self.station,
            "station_id": self.station_id,
            "tn_c": self.tn_c,
            "tx_c": self.tx_c,
            "t12_c": self.t12_c,
            "rr06_mm": self.rr06_mm,
            "rr12_mm": self.rr12_mm,
            "rr18_mm": self.rr18_mm,
            "hu06_pct": self.hu06_pct,
            "hu12_pct": self.hu12_pct,
            "hu18_pct": self.hu18_pct,
            "source_file": self.source_file,
        }


# Labels with user glossary meanings
DAILY_METRIC_LINES = {
    Metric.TN: ("tn_c", "TN (température minimale)", "{:.1f}°C", "non renseignée"),
    Metric.TX: ("tx_c", "TX (température maximale)", "{:.1f}°C", "non renseignée"),
    Metric.T12: ("t12_c", "T12 (température à midi)", "{:.1f}°C", "non renseignée"),
    Metric.RR06: (
        "rr06_mm",
        "RR06 (précipitations 06h j-1 → 06h j)",
        "{:.1f} mm",
        "non renseignée / nulle",
    ),
    Metric.RR12: (
        "rr12_mm",
        "RR12 (précipitations 00h → 12h)",
        "{:.1f} mm",
        "non renseignée / nulle",
    ),
    Metric.RR18: (
        "rr18_mm",
        "RR18 (précipitations à 18h)",
        "{:.1f} mm",
        "non renseignée / nulle",
    ),
    Metric.HU06: ("hu06_pct", "Hu06 (humidité à 06h)", "{:.0f}%", "non renseignée"),
    Metric.HU12: ("hu12_pct", "Hu12 (humidité à 12h)", "{:.0f}%", "non renseignée"),
    Metric.HU18: ("hu18_pct", "Hu18 (humidité à 18h)", "{:.0f}%", "non renseignée"),
}


class DailyObsStore:
    """Local DRMNO daily observations (OBSMET-JOUR)."""

    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self.bulletins: list[dict] = []
        self.stations: list[dict] = []
        self.glossary: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.data_path.exists():
            self.bulletins = []
            self.stations = []
            self.glossary = {}
            return
        payload = json.loads(self.data_path.read_text(encoding="utf-8"))
        self.bulletins = payload.get("bulletins") or []
        self.stations = payload.get("stations") or []
        self.glossary = payload.get("glossary") or {}

    @property
    def available(self) -> bool:
        return bool(self.bulletins)

    def list_station_names(self) -> list[str]:
        return sorted({s["station"] for s in self.stations if s.get("station")})

    def match_station(self, query: str) -> dict | None:
        needle = normalize(query)
        if not needle:
            return None
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

    def bulletin_for_date(self, date: str | None) -> dict | None:
        if not self.bulletins:
            return None
        if date is None:
            return self.bulletins[-1]
        for bulletin in reversed(self.bulletins):
            if bulletin.get("date") == date:
                return bulletin
        return None

    def get_observation(self, place: str, date: str | None = None) -> DailyObsHit | None:
        bulletin = self.bulletin_for_date(date)
        if bulletin is None:
            return None

        hit = self._hit_from_bulletin(bulletin, place)
        if hit is not None:
            return hit

        # Station may be absent that day: fall back to nearest bulletin containing it
        for candidate in reversed(self.bulletins):
            if date is not None and candidate.get("date") == date:
                continue
            hit = self._hit_from_bulletin(candidate, place)
            if hit is not None:
                return hit
        return None

    def _hit_from_bulletin(self, bulletin: dict, place: str) -> DailyObsHit | None:
        needle = normalize(place)
        if not needle:
            return None

        rows = bulletin.get("stations") or []
        best: tuple[int, dict] | None = None
        for row in rows:
            name = normalize(row.get("station") or "")
            province = normalize(row.get("province") or "")
            sid = (row.get("station_id") or "").lower()
            score = 0
            if needle == name or needle == sid:
                score = 100
            elif needle in name or name in needle:
                score = 80
            elif needle in province:
                score = 40
            if score and (best is None or score > best[0]):
                best = (score, row)

        if best is None:
            return None
        row = best[1]
        return DailyObsHit(
            date=bulletin["date"],
            province=row.get("province") or "",
            station=row.get("station") or "",
            station_id=row.get("station_id"),
            tn_c=row.get("tn_c"),
            tx_c=row.get("tx_c"),
            t12_c=row.get("t12_c"),
            rr06_mm=row.get("rr06_mm"),
            rr12_mm=row.get("rr12_mm"),
            rr18_mm=row.get("rr18_mm"),
            hu06_pct=row.get("hu06_pct"),
            hu12_pct=row.get("hu12_pct"),
            hu18_pct=row.get("hu18_pct"),
            source_file=bulletin.get("source_file") or "",
        )
    def _format_metric_line(self, hit: DailyObsHit, metric: Metric) -> str | None:
        spec = DAILY_METRIC_LINES.get(metric)
        if spec is None:
            return None
        attr, label, fmt, missing = spec
        value = getattr(hit, attr)
        if value is None:
            return f"{label} : {missing}"
        return f"{label} : {fmt.format(value)}"

    def format_observation(
        self,
        hit: DailyObsHit,
        metric: Metric | str | None = None,
    ) -> str:
        """STRICT FILTERING: targeted metric → only that field + header/source."""
        key = metric.value if isinstance(metric, Metric) else metric
        if key:
            try:
                metric_enum = metric if isinstance(metric, Metric) else Metric(key)
            except ValueError:
                metric_enum = None
            if metric_enum is not None:
                line = self._format_metric_line(hit, metric_enum)
                if line is not None:
                    return styled_reply(
                        title=f"Observation DRMNO quotidienne — {hit.station} ({hit.province})",
                        meta=[f"Date : {hit.date}"],
                        body_lines=[line],
                        source=hit.source_file,
                    )

        body: list[str] = []
        for metric_enum in (
            Metric.TN,
            Metric.TX,
            Metric.T12,
            Metric.HU06,
            Metric.HU12,
            Metric.HU18,
            Metric.RR06,
            Metric.RR12,
            Metric.RR18,
        ):
            line = self._format_metric_line(hit, metric_enum)
            if line:
                attr = DAILY_METRIC_LINES[metric_enum][0]
                value = getattr(hit, attr)
                if value is None and attr.startswith("rr"):
                    continue
                body.append(line)
        return styled_reply(
            title=f"Observation DRMNO quotidienne — {hit.station} ({hit.province})",
            meta=[f"Date : {hit.date}"],
            body_lines=body,
            source=hit.source_file,
        )
