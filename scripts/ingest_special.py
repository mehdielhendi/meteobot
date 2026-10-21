"""Ingest SPECIAL forecast PDFs (Bulletin Météorologique Spécial)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pdfplumber

FILENAME_RE = re.compile(
    r"SPECIAL_(.+?)_(\d{2})h_(\d{8})\.pdf",
    re.IGNORECASE,
)


def city_from_token(token: str) -> str:
    return token.replace("_", " ").replace("-", " ").strip().title()


def parse_filename(path: Path) -> dict | None:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None
    city_token, horizon, ymd = match.groups()
    return {
        "city": city_from_token(city_token),
        "city_key": city_token.upper(),
        "horizon_h": int(horizon),
        "issue_date": f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}",
        "source_file": path.name,
    }


def cell(value) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def extract_issued_label(text: str) -> str | None:
    m = re.search(r"Etabli le\s+(.+)", text, re.IGNORECASE)
    return cell(m.group(1)) if m else None


def parse_special_table(table: list[list], meta: dict, issued_label: str | None) -> dict:
    """Normalize SPECIAL table into period slots."""
    if not table or len(table) < 3:
        return {**meta, "issued_label": issued_label, "periods": [], "raw_rows": table}

    # Detect header rows for period labels / slots
    header0 = [cell(c) for c in table[0]]
    header1 = [cell(c) for c in table[1]] if len(table) > 1 else []

    # Build column labels from day + slot
    col_labels: list[str] = []
    current_day = None
    max_cols = max(len(r) for r in table)
    for idx in range(1, max_cols):
        day = header0[idx] if idx < len(header0) else None
        if day:
            current_day = day
        slot = header1[idx] if idx < len(header1) else None
        if current_day and slot:
            col_labels.append(f"{current_day} | {slot}")
        elif slot:
            col_labels.append(slot)
        elif current_day:
            col_labels.append(current_day)
        else:
            col_labels.append(f"col_{idx}")

    # Map row label -> values
    fields: dict[str, list[str | None]] = {}

    for row in table[2:]:
        label = cell(row[0]) if row else None
        values = [cell(v) for v in row[1:1 + len(col_labels)]]
        # pad
        while len(values) < len(col_labels):
            values.append(None)

        if label is None and "vent" in fields and any(values):
            # continuation of previous vent row (speeds)
            merged = []
            prev = fields["vent"]
            for i, speed in enumerate(values):
                base = prev[i] if i < len(prev) else None
                if base and speed:
                    merged.append(f"{base} {speed}")
                else:
                    merged.append(base or speed)
            fields["vent"] = merged
            continue

        if not label:
            continue

        key = label.lower()
        if "etat du ciel" in key or "état du ciel" in key:
            fields["sky"] = values
        elif "phenomene" in key or "phénomène" in key or "phenomenes" in key or "phénomènes" in key:
            fields["phenomena"] = values
        elif key.startswith("vent"):
            fields["vent"] = values
        elif "temp" in key and "min" in key:
            fields["tmin"] = values
        elif "temp" in key and "max" in key:
            fields["tmax"] = values
        elif "t.extr" in key or "extrême" in key or "extreme" in key:
            fields["textremes"] = values
        elif "pluie" in key:
            fields["rain"] = values
        else:
            fields[key] = values

    periods = []
    for i, label in enumerate(col_labels):
        period = {"label": label}
        for field_name, values in fields.items():
            if i < len(values) and values[i] is not None:
                period[field_name] = values[i]
        periods.append(period)

    return {
        **meta,
        "issued_label": issued_label,
        "periods": periods,
    }


def extract_special(path: Path) -> dict | None:
    meta = parse_filename(path)
    if meta is None:
        return None
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ""
        tables = page.extract_tables() or []
    issued = extract_issued_label(text)
    if tables:
        return parse_special_table(tables[0], meta, issued)
    return {**meta, "issued_label": issued, "periods": [], "raw_text": text}


def ingest_folder(source_dir: Path, output_path: Path) -> dict:
    forecasts = []
    for path in sorted(source_dir.glob("SPECIAL_*.pdf")):
        item = extract_special(path)
        if item is not None:
            forecasts.append(item)

    forecasts.sort(key=lambda f: (f.get("issue_date") or "", f.get("city") or ""))
    cities = sorted({f["city"] for f in forecasts if f.get("city")})

    payload = {
        "source_dir": str(source_dir),
        "forecast_count": len(forecasts),
        "city_count": len(cities),
        "cities": cities,
        "forecasts": forecasts,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = Path(r"sources/bulletins")
    output = root / "data" / "obs" / "special_forecasts.json"
    payload = ingest_folder(source, output)
    print(
        f"Ingested {payload['forecast_count']} SPECIAL forecasts, "
        f"{payload['city_count']} cities -> {output}"
    )


if __name__ == "__main__":
    main()
