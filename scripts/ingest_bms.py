"""Ingest BMS (Bulletin d'Alerte Météorologique) PDFs."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pdfplumber

FILENAME_RE = re.compile(
    r"BMSGeneral[_-](\d{8}|\d{2}\d{2}\d{4})\.pdf",
    re.IGNORECASE,
)


def parse_issue_date(name: str) -> str | None:
    """Return YYYY-MM-DD from filename variants."""
    m = re.search(r"(\d{8})", name)
    if not m:
        return None
    raw = m.group(1)
    # Prefer YYYYMMDD when year starts with 20
    if raw.startswith("20"):
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    # DDMMYYYY
    return f"{raw[4:8]}-{raw[2:4]}-{raw[0:2]}"


def clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def parse_bms_text(text: str, source_file: str, issue_date: str | None) -> dict:
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    full = "\n".join(lines)

    nr_match = re.search(r"NR\s*:\s*([0-9/]+)", full, re.IGNORECASE)
    bam_match = re.search(r"BAM\s*N[°º]?\s*:\s*([0-9/]+)", full, re.IGNORECASE)
    etabli_match = re.search(r"ÉTABLI LE\s*:\s*(.+)", full, re.IGNORECASE)

    # Split phenomena blocks starting with "I -", "II -", ...
    blocks = re.split(r"(?=\b(?:I{1,3}|IV|V|VI|VII|VIII|IX|X)\s*-\s*Type de ph[ée]nom[èe]ne\s*:)", full)
    phenomena: list[dict] = []

    for block in blocks:
        if not re.search(r"Type de ph[ée]nom[èe]ne\s*:", block, re.IGNORECASE):
            continue

        type_m = re.search(
            r"Type de ph[ée]nom[èe]ne\s*:\s*(.+?)(?:\n|-Niveau)",
            block,
            re.IGNORECASE | re.DOTALL,
        )
        level_m = re.search(
            r"Niveau de vigilance\s*:\s*([^\n]+)",
            block,
            re.IGNORECASE,
        )

        # One phenomenon can have several province groups + periods
        groups: list[dict] = []
        # Find intensity lines like "60 - 95 mm : provinces..." or "43/45 °C : ..."
        intensity_iter = list(
            re.finditer(
                r"(?m)^(\d+\s*[/\-]\s*\d+\s*(?:mm|km/h|°C|C)?)\s*:\s*(.+?)(?=(?:\n\d+\s*[/\-]\s*\d+|\n-Début|\n\*Provinces|\nII\s*-|\nIII\s*-|\Z))",
                block,
                re.IGNORECASE | re.DOTALL,
            )
        )

        # Periods after each intensity or shared
        periods = re.findall(
            r"D[ée]but et fin du ph[ée]nom[èe]ne\s*:\s*(.+?)(?=\n\*Provinces|\n\d+\s*[/\-]|\nII\s*-|\nIII\s*-|\nPage|\Z)",
            block,
            re.IGNORECASE | re.DOTALL,
        )
        periods = [clean(p.replace("\n", " ")) for p in periods]

        if intensity_iter:
            for idx, match in enumerate(intensity_iter):
                intensity = clean(match.group(1))
                provinces_raw = clean(match.group(2).replace("\n", " "))
                provinces = [
                    clean(p).rstrip(".")
                    for p in re.split(r",| et ", provinces_raw)
                    if clean(p).rstrip(".")
                ]
                period = periods[idx] if idx < len(periods) else (periods[-1] if periods else None)
                groups.append(
                    {
                        "intensity": intensity,
                        "provinces": provinces,
                        "period": period,
                    }
                )
        else:
            # fallback: collect provinces line after "*Provinces concernées"
            prov_m = re.search(
                r"Provinces concern[ée]es\s*(.+?)(?:D[ée]but et fin|\Z)",
                block,
                re.IGNORECASE | re.DOTALL,
            )
            provinces = []
            if prov_m:
                provinces_raw = clean(prov_m.group(1).replace("\n", " "))
                provinces = [
                    clean(p).rstrip(".")
                    for p in re.split(r",| et ", provinces_raw)
                    if clean(p).rstrip(".") and not p.lower().startswith("début")
                ]
            groups.append(
                {
                    "intensity": None,
                    "provinces": provinces,
                    "period": periods[0] if periods else None,
                }
            )

        phenomena.append(
            {
                "type": clean(type_m.group(1)) if type_m else None,
                "vigilance_level": clean(level_m.group(1)) if level_m else None,
                "groups": groups,
            }
        )

    return {
        "source_file": source_file,
        "issue_date": issue_date,
        "bulletin_nr": nr_match.group(1) if nr_match else None,
        "bam_nr": bam_match.group(1) if bam_match else None,
        "issued_label": clean(etabli_match.group(1)) if etabli_match else None,
        "phenomena": phenomena,
        "raw_text": full,
    }


def extract_bms(path: Path) -> dict:
    with pdfplumber.open(path) as pdf:
        text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    return parse_bms_text(text, path.name, parse_issue_date(path.name))


def ingest_folder(source_dir: Path, output_path: Path) -> dict:
    bulletins = []
    for path in sorted(source_dir.glob("BMSGeneral*.pdf")):
        bulletins.append(extract_bms(path))
    bulletins.sort(key=lambda b: b.get("issue_date") or "")

    payload = {
        "source_dir": str(source_dir),
        "bulletin_count": len(bulletins),
        "bulletins": bulletins,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = Path(r"sources/bulletins")
    output = root / "data" / "obs" / "bms_alerts.json"
    payload = ingest_folder(source, output)
    print(f"Ingested {payload['bulletin_count']} BMS bulletins -> {output}")


if __name__ == "__main__":
    main()
