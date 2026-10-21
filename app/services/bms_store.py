from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from app.services.reply_style import styled_reply


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFD", text.lower())
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


PLACE_ALIASES: dict[str, tuple[str, ...]] = {
    "ouazzane": ("ouezzane", "ouazzane"),
    "ouezzane": ("ouezzane", "ouazzane"),
    "tetouan": ("tetouan", "tetuan"),
    "al hoceima": ("al hoceima", "al houceima", "alhoceima"),
    "kenitra": ("kenitra",),
    "khemisset": ("khemisset", "khmissat"),
    "temara": ("temara", "skhirat temara"),
}

LEVEL_RANK = {
    "vert": 0,
    "green": 0,
    "jaune": 1,
    "yellow": 1,
    "orange": 2,
    "rouge": 3,
    "red": 3,
}


def normalize_level(level: str | None) -> str:
    if not level:
        return "vert"
    low = normalize(str(level))
    if "rouge" in low or low == "red":
        return "rouge"
    if "orange" in low:
        return "orange"
    if "jaune" in low or low == "yellow":
        return "jaune"
    if "vert" in low or low == "green":
        return "vert"
    return "vert"


class BmsStore:
    """Local BMS alert bulletins (niveau de vigilance)."""

    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self.bulletins: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.data_path.exists():
            self.bulletins = []
            return
        payload = json.loads(self.data_path.read_text(encoding="utf-8"))
        self.bulletins = payload.get("bulletins") or []

    @property
    def available(self) -> bool:
        return bool(self.bulletins)

    def latest(self) -> dict | None:
        return self.bulletins[-1] if self.bulletins else None

    def for_date(self, date: str | None) -> dict | None:
        if not self.bulletins:
            return None
        if date is None:
            return self.latest()
        for bulletin in reversed(self.bulletins):
            if bulletin.get("issue_date") == date:
                return bulletin
        return None

    def _place_needles(self, place: str) -> list[str]:
        needle = normalize(place)
        aliases = PLACE_ALIASES.get(needle, ())
        out = [needle, *aliases]
        seen: set[str] = set()
        uniq: list[str] = []
        for item in out:
            if item and item not in seen:
                seen.add(item)
                uniq.append(item)
        return uniq

    def _province_matches(self, place: str, province: str) -> bool:
        pname = normalize(province)
        for needle in self._place_needles(place):
            if needle == pname or needle in pname or pname in needle:
                return True
        return False

    def find_for_place(self, place: str, date: str | None = None) -> list[dict]:
        """Return matching alert snippets for a province/city name."""
        bulletin = self.for_date(date)
        if bulletin is None:
            return []
        needle = normalize(place)
        hits: list[dict] = []
        for ph in bulletin.get("phenomena") or []:
            for group in ph.get("groups") or []:
                matched = []
                for province in group.get("provinces") or []:
                    if self._province_matches(place, province):
                        matched.append(province)
                if matched or not needle:
                    hits.append(
                        {
                            "type": ph.get("type"),
                            "vigilance_level": ph.get("vigilance_level"),
                            "intensity": group.get("intensity"),
                            "provinces": matched or group.get("provinces"),
                            "period": group.get("period"),
                            "issue_date": bulletin.get("issue_date"),
                            "bulletin_nr": bulletin.get("bulletin_nr"),
                            "source_file": bulletin.get("source_file"),
                            "issued_label": bulletin.get("issued_label"),
                        }
                    )
        return hits

    def level_for_place(self, place: str, date: str | None = None) -> dict:
        """Highest current vigilance for a place in the selected bulletin."""
        hits = self.find_for_place(place, date)
        if not hits:
            return {"level": "vert", "type": None, "active": False}
        best = hits[0]
        best_rank = LEVEL_RANK.get(normalize_level(best.get("vigilance_level")), -1)
        for hit in hits[1:]:
            rank = LEVEL_RANK.get(normalize_level(hit.get("vigilance_level")), -1)
            if rank > best_rank:
                best = hit
                best_rank = rank
        level = normalize_level(best.get("vigilance_level"))
        return {
            "level": level,
            "type": best.get("type"),
            "active": level != "vert",
            "intensity": best.get("intensity"),
        }

    def vigilance_overview(self, places: list[str], date: str | None = None) -> dict:
        bulletin = self.for_date(date)
        place_map: dict[str, dict] = {}
        active_places: list[str] = []
        for place in places:
            info = self.level_for_place(
                place, bulletin.get("issue_date") if bulletin else date
            )
            place_map[place] = info
            if info.get("active"):
                active_places.append(place)
        phenomena = []
        if bulletin:
            for ph in bulletin.get("phenomena") or []:
                phenomena.append(
                    {
                        "type": ph.get("type"),
                        "level": normalize_level(ph.get("vigilance_level")),
                    }
                )
        return {
            "issue_date": bulletin.get("issue_date") if bulletin else None,
            "bulletin_nr": bulletin.get("bulletin_nr") if bulletin else None,
            "issued_label": bulletin.get("issued_label") if bulletin else None,
            "places": place_map,
            "active_count": len(active_places),
            "active_places": active_places,
            "phenomena": phenomena,
        }

    def format_bulletin(self, bulletin: dict, place: str | None = None) -> str:
        if place:
            hits = self.find_for_place(place, bulletin.get("issue_date"))
            if not hits:
                return (
                    f"Aucune alerte BMS trouvée pour « {place} » "
                    f"dans {bulletin.get('source_file')} "
                    f"(NR {bulletin.get('bulletin_nr')})."
                )
            sections: list[tuple[str, list[str]]] = []
            for hit in hits:
                level = normalize_level(hit.get("vigilance_level"))
                fields = [f"Vigilance : {level.upper()}"]
                if hit.get("intensity"):
                    fields.append(f"Intensité : {hit['intensity']}")
                fields.append(f"Provinces : {', '.join(hit.get('provinces') or [])}")
                if hit.get("period"):
                    fields.append(f"Période : {hit['period']}")
                sections.append((f"Phénomène : {hit.get('type')}", fields))
            return styled_reply(
                title=f"Alerte BMS — NR {bulletin.get('bulletin_nr')} ({bulletin.get('issue_date')})",
                meta=[
                    f"Établi : {bulletin.get('issued_label')}",
                    f"Zone demandée : {place}",
                ],
                sections=sections,
                source=bulletin.get("source_file"),
            )

        sections = []
        for ph in bulletin.get("phenomena") or []:
            level = normalize_level(ph.get("vigilance_level"))
            fields = [f"Vigilance : {level.upper()}"]
            for group in ph.get("groups") or []:
                if group.get("intensity"):
                    fields.append(
                        f"{group['intensity']} : {', '.join(group.get('provinces') or [])}"
                    )
                else:
                    fields.append(
                        f"Provinces : {', '.join(group.get('provinces') or [])}"
                    )
                if group.get("period"):
                    fields.append(f"Période : {group['period']}")
            sections.append((f"Phénomène : {ph.get('type')}", fields))
        return styled_reply(
            title=(
                f"Bulletin d'alerte BMS — NR {bulletin.get('bulletin_nr')} "
                f"(BAM {bulletin.get('bam_nr')})"
            ),
            meta=[
                f"Date : {bulletin.get('issue_date')}",
                f"Établi : {bulletin.get('issued_label')}",
            ],
            sections=sections,
            source=bulletin.get("source_file"),
        )
