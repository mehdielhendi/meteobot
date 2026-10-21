"""Ingest DRMNO daily (quotidienne) observation PDFs into JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pdfplumber

FILENAME_RE = re.compile(r"OBSMET-JOUR-(\d{2})(\d{2})(\d{4})\.pdf", re.IGNORECASE)
STATION_ID_RE = re.compile(r"\((\d{5})\)\s*$")

# Glossary (DRMNO daily bulletins)
GLOSSARY = {
    "Tn": "Température minimale (°C)",
    "Tx": "Température maximale (°C)",
    "T12": "Température à midi (°C)",
    "Rr06": "Précipitations de 06h (j-1) à 06h (j), en mm",
    "Rr12": "Précipitations de 00h à 12h (j), en mm",
    "Rr18": "Précipitations à 18h (j), en mm",
    "Hu06": "Humidité à 06h (%)",
    "Hu12": "Humidité à 12h (%)",
    "Hu18": "Humidité à 18h (%)",
    "Vent": "Vent en nœuds (kt) ; 1 kt ≈ 1,85 km/h (~2 km/h)",
    "W": "Vent d'ouest (West)",
    "CAL": "Calme (pas de vent)",
}


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_station_name(raw: str | None) -> tuple[str, str | None]:
    text = (raw or "").strip()
    match = STATION_ID_RE.search(text)
    if not match:
        return text.replace("_", " "), None
    station_id = match.group(1)
    name = STATION_ID_RE.sub("", text).strip().replace("_", " ")
    return name, station_id


def parse_filename(path: Path) -> dict | None:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None
    day, month, year = match.groups()
    return {
        "date": f"{year}-{month}-{day}",
        "source_file": path.name,
    }


def extract_bulletin(path: Path) -> dict | None:
    meta = parse_filename(path)
    if meta is None:
        return None

    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        tables = page.extract_tables() or []

    if not tables:
        return {**meta, "stations": []}

    rows = tables[0]
    stations: list[dict] = []
    for row in rows[1:]:
        if not row or len(row) < 11:
            continue
        province = (row[0] or "").strip()
        name, station_id = parse_station_name(row[1])
        if not name:
            continue
        stations.append(
            {
                "province": province,
                "station": name,
                "station_id": station_id,
                "tn_c": parse_float(row[2]),
                "rr06_mm": parse_float(row[3]),
                "hu06_pct": parse_float(row[4]),
                "t12_c": parse_float(row[5]),
                "rr12_mm": parse_float(row[6]),
                "hu12_pct": parse_float(row[7]),
                "tx_c": parse_float(row[8]),
                "rr18_mm": parse_float(row[9]),
                "hu18_pct": parse_float(row[10]),
            }
        )
    return {**meta, "stations": stations}


def ingest_folder(source_dir: Path, output_path: Path) -> dict:
    bulletins: list[dict] = []
    for path in sorted(source_dir.glob("OBSMET-JOUR-*.pdf")):
        bulletin = extract_bulletin(path)
        if bulletin is not None:
            bulletins.append(bulletin)

    bulletins.sort(key=lambda item: item["date"])
    station_index: dict[str, dict] = {}
    for bulletin in bulletins:
        for station in bulletin["stations"]:
            key = (station.get("station_id") or station["station"]).lower()
            station_index[key] = {
                "station": station["station"],
                "station_id": station.get("station_id"),
                "province": station.get("province"),
            }

    payload = {
        "source_dir": str(source_dir),
        "glossary": GLOSSARY,
        "bulletin_count": len(bulletins),
        "station_count": len(station_index),
        "stations": list(station_index.values()),
        "bulletins": bulletins,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = Path(r"sources/obs_quotidienne")
    output = root / "data" / "obs" / "daily.json"
    payload = ingest_folder(source, output)
    print(
        f"Ingested {payload['bulletin_count']} daily bulletins, "
        f"{payload['station_count']} stations -> {output}"
    )


if __name__ == "__main__":
    main()
