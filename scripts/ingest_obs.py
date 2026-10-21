"""Ingest DRMNO hourly observation PDFs into a structured JSON store."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pdfplumber

FILENAME_RE = re.compile(
    r"OBSMET-HORAIRE-(\d{2})(\d{2})(\d{4})-(\d{2})h(\d{2})\.pdf",
    re.IGNORECASE,
)
STATION_ID_RE = re.compile(r"\((\d{5})\)\s*$")


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
        return text, None
    station_id = match.group(1)
    name = STATION_ID_RE.sub("", text).strip()
    return name, station_id


def parse_filename(path: Path) -> dict | None:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None
    day, month, year, hour, minute = match.groups()
    return {
        "date": f"{year}-{month}-{day}",
        "time": f"{hour}:{minute}",
        "hour": int(hour),
        "minute": int(minute),
        "datetime": f"{year}-{month}-{day}T{hour}:{minute}:00",
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
        if not row or len(row) < 8:
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
                "temperature_c": parse_float(row[2]),
                "dew_point_c": parse_float(row[3]),
                "humidity_pct": parse_float(row[4]),
                "visibility_km": parse_float(row[5]),
                "pressure_hpa": parse_float(row[6]),
                "wind": (row[7] or "").strip() or None,
                "rain_mm": parse_float(row[8]) if len(row) > 8 else None,
                "snow_cm": parse_float(row[9]) if len(row) > 9 else None,
            }
        )

    return {**meta, "stations": stations}


def ingest_folder(source_dir: Path, output_path: Path) -> dict:
    bulletins: list[dict] = []
    for path in sorted(source_dir.glob("OBSMET-HORAIRE-*.pdf")):
        bulletin = extract_bulletin(path)
        if bulletin is not None:
            bulletins.append(bulletin)

    bulletins.sort(key=lambda item: item["datetime"])
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
    source = Path(r"sources/obs_horaire")
    output = root / "data" / "obs" / "hourly.json"
    payload = ingest_folder(source, output)
    print(
        f"Ingested {payload['bulletin_count']} bulletins, "
        f"{payload['station_count']} stations -> {output}"
    )


if __name__ == "__main__":
    main()
