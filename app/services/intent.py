from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

from app.models import Intent


class Metric(str, Enum):
    # Hourly OBS
    TEMPERATURE = "temperature"
    DEW_POINT = "dew_point"
    HUMIDITY = "humidity"
    VISIBILITY = "visibility"
    PRESSURE = "pressure"
    WIND = "wind"
    RAIN = "rain"
    SNOW = "snow"
    # Daily OBS (OBSMET-JOUR)
    TN = "tn"  # température minimale
    TX = "tx"  # température maximale
    T12 = "t12"  # température à midi
    RR06 = "rr06"  # précip. 06h j-1 → 06h j
    RR12 = "rr12"  # précip. 00h → 12h
    RR18 = "rr18"  # précip. à 18h
    HU06 = "hu06"  # humidité à 06h
    HU12 = "hu12"  # humidité à 12h
    HU18 = "hu18"  # humidité à 18h
    # SPECIAL forecasts
    TEXTREMES = "textremes"  # températures extrêmes (mini/maxi prévues)
    SKY = "sky"  # état du ciel
    PHENOMENA = "phenomena"  # phénomènes


DAILY_METRICS = {
    Metric.TN,
    Metric.TX,
    Metric.T12,
    Metric.RR06,
    Metric.RR12,
    Metric.RR18,
    Metric.HU06,
    Metric.HU12,
    Metric.HU18,
}


# STRICT FILTERING RULE: if a targeted parameter is requested, answer ONLY
# with that parameter (+ location, date/time, source). General queries
# ("Météo à …") keep the full observation summary.
METRIC_KEYWORDS: dict[Metric, tuple[str, ...]] = {
    Metric.TEMPERATURE: (
        "température",
        "temperature",
        "températures",
        "temperatures",
        "temp ",
        "temps qu'il fait",
    ),
    Metric.DEW_POINT: (
        "point de rosée",
        "point de rosee",
        "rosée",
        "rosee",
        "dew point",
        "dewpoint",
    ),
    Metric.HUMIDITY: (
        "humidité",
        "humidite",
        "humidity",
        "hum ",
    ),
    Metric.VISIBILITY: (
        "visibilité",
        "visibilite",
        "visibility",
        "vis ",
    ),
    Metric.PRESSURE: (
        "pression",
        "pressure",
        "hpa",
        "hectopascal",
    ),
    Metric.WIND: (
        "vent",
        "vents",
        "wind",
        "rafale",
        "rafales",
    ),
    Metric.RAIN: (
        "pluie",
        "pluies",
        "pluviométrie",
        "pluviometrie",
        "precipitation",
        "précipitation",
        "précipitations",
        "precipitations",
        "rain",
    ),
    Metric.SNOW: (
        "neige",
        "neiges",
        "snow",
    ),
}

HOUR_PATTERN = re.compile(
    r"\b(?:à\s*)?(\d{1,2})\s*h(?:eures?)?(?:\s*(\d{2}))?\b|\b(\d{1,2}):(\d{2})\b",
    re.IGNORECASE,
)

INTENT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.CURRENT: (
        "maintenant",
        "actuel",
        "actuelle",
        "temps",
        "météo",
        "meteo",
        "température",
        "temperature",
        "aujourd'hui",
        "observation",
        "observations",
        "bulletin",
        "horaire",
        "quotidien",
        "quotidienne",
        "journalier",
        "journalière",
        "conditions",
        "humidité",
        "humidite",
        "pression",
        "vent",
        "visibilité",
        "visibilite",
        "précipitation",
        "precipitation",
        "pluie",
        "tn",
        "tx",
        "t12",
        "rr06",
        "rr12",
        "rr18",
    ),
    Intent.FORECAST: (
        "prévision",
        "prevision",
        "prévisions",
        "previsions",
        "demain",
        "semaine",
        "forecast",
        "à venir",
        "a venir",
        "special",
        "spécial",
        "après-demain",
        "apres-demain",
    ),
    Intent.ALERTS: (
        "alerte",
        "alertes",
        "vigilance",
        "orage",
        "tempête",
        "tempete",
        "danger",
        "avis",
        "bms",
        "bam",
        "niveau d'alerte",
        "rafales",
        "vague de chaleur",
    ),
    Intent.CLIMATE: (
        "climat",
        "historique",
        "moyenne",
        "climatologique",
        "années",
        "annees",
        "passé",
        "passe",
    ),
    Intent.HELP: (
        "aide",
        "help",
        "que peux-tu",
        "comment",
        "capacités",
        "capacites",
        "stations",
        "liste",
    ),
}

STOPWORDS = {
    "quel",
    "quelle",
    "temps",
    "meteo",
    "météo",
    "aujourd",
    "demain",
    "semaine",
    "aide",
    "alerte",
    "alertes",
    "prevision",
    "prévision",
    "donne",
    "donne-moi",
    "peux",
    "veux",
    "bonjour",
    "merci",
    "s'il",
    "sil",
    "vous",
    "moi",
    "les",
    "des",
    "une",
    "pour",
    "dans",
    "avec",
    "sur",
    "fait",
    "observation",
    "observations",
    "bulletin",
    "horaire",
    "temperature",
    "température",
    "humidite",
    "humidité",
    "pression",
    "vent",
}


@dataclass
class ParsedQuery:
    intent: Intent
    city: str | None
    hour: int | None
    date: str | None
    metric: Metric | None
    dataset: str  # "hourly" | "daily" | "auto" | "bms" | "special"
    day_filter: str | None
    cities: list[str]
    compare: bool
    raw: str


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFD", text.lower())
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def extract_metric(message: str) -> Metric | None:
    """Return a targeted weather parameter if the user asked for one only."""
    text = message.lower()

    # SPECIAL: températures extrêmes (forecast mini/maxi)
    if re.search(
        r"temp[ée]ratures?\s+extr[êe]mes?|\bt\.?\s*extr[êe]mes?\b|\bextremes?\b",
        text,
    ):
        return Metric.TEXTREMES
    if re.search(r"[ée]tat\s+du\s+ciel|\bciel\b", text):
        return Metric.SKY
    if re.search(r"ph[ée]nom[èe]nes?", text):
        return Metric.PHENOMENA

    # --- Daily bulletin codes / meanings first ---
    if re.search(r"\btn\b|temp[ée]rature\s+minimale|temp\s*min", text):
        return Metric.TN
    if re.search(r"\btx\b|temp[ée]rature\s+maximale|temp\s*max", text):
        return Metric.TX
    if re.search(r"\bt12\b|temp[ée]rature\s+[àa]\s+midi|[àa]\s+midi", text):
        return Metric.T12
    if re.search(r"\brr06\b|pr[ée]cip(?:itation)?s?\s+(?:[àa]\s+)?06", text):
        return Metric.RR06
    if re.search(r"\brr12\b|pr[ée]cip(?:itation)?s?\s+(?:[àa]\s+)?12", text):
        return Metric.RR12
    if re.search(r"\brr18\b|pr[ée]cip(?:itation)?s?\s+(?:[àa]\s+)?18", text):
        return Metric.RR18
    if re.search(r"\bhu06\b|humidit[ée]\s+de\s+06", text):
        return Metric.HU06
    if re.search(r"\bhu12\b|humidit[ée]\s+de\s+12", text):
        return Metric.HU12
    if re.search(r"\bhu18\b|humidit[ée]\s+de\s+18", text):
        return Metric.HU18

    # Rain / precip (codes already handled above)
    if re.search(
        r"\bpluies?\b|\bpluviom[ée]trie\b|\bpr[ée]cipitations?\b|\brain\b",
        text,
    ):
        if any(k in text for k in ("quotidien", "journalier", "journalière", "du jour")):
            return Metric.RR12
        return Metric.RAIN

    if re.search(r"\bhumidit[ée]\b|\bhumidity\b", text):
        return Metric.HUMIDITY

    if re.search(r"\btemp(?:[ée]rature|erature|s)?\b", text):
        return Metric.TEMPERATURE
    if "point de rosée" in text or "point de rosee" in text or "dew point" in text:
        return Metric.DEW_POINT
    if re.search(r"\bvisibilit[ée]\b|\bvisibility\b", text):
        return Metric.VISIBILITY
    if re.search(r"\bpression\b|\bpressure\b|\bhpa\b", text):
        return Metric.PRESSURE
    if re.search(r"\bvents?\b|\bwind\b|\brafales?\b|\bcal\b|\bcalme\b|\bvitesse\b", text):
        return Metric.WIND
    if re.search(r"\bneiges?\b|\bsnow\b", text):
        return Metric.SNOW
    return None


def extract_date(message: str) -> str | None:
    """Extract calendar date as YYYY-MM-DD when present."""
    text = message.lower()

    m = re.search(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b", text)
    if m:
        day, month, year = m.groups()
        return f"{year}-{month}-{day}"

    m = re.search(r"\b(\d{2})(\d{2})(\d{4})\b", text)
    if m:
        day, month, year = m.groups()
        return f"{year}-{month}-{day}"

    months = {
        "janvier": "01",
        "fevrier": "02",
        "février": "02",
        "mars": "03",
        "avril": "04",
        "mai": "05",
        "juin": "06",
        "juillet": "07",
        "aout": "08",
        "août": "08",
        "septembre": "09",
        "octobre": "10",
        "novembre": "11",
        "decembre": "12",
        "décembre": "12",
    }
    m = re.search(
        r"\b(\d{1,2})\s+(" + "|".join(months.keys()) + r")(?:\s+(\d{4}))?\b",
        text,
    )
    if m:
        day = int(m.group(1))
        month = months[m.group(2)]
        year = m.group(3) or "2026"
        return f"{year}-{month}-{day:02d}"
    return None


def extract_day_filter(message: str) -> str | None:
    text = message.lower()
    if "après-demain" in text or "apres-demain" in text or "après demain" in text:
        return "Après-Demain"
    if re.search(r"\bdemain\b", text):
        return "Demain"
    if "aujourd'hui" in text or "aujourdhui" in text:
        return "Aujourd'hui"
    return None


def detect_dataset(message: str, metric: Metric | None, hour: int | None, date: str | None) -> str:
    text = message.lower()
    if any(token in text for token in ("bms", "vigilance", "alerte", "bam", "niveau d'alerte")):
        return "bms"
    if any(
        token in text
        for token in (
            "special",
            "spécial",
            "prévision",
            "prevision",
            "prévisions",
            "previsions",
            "prévu",
            "prevu",
            "prévue",
            "prevue",
            "forecast",
        )
    ):
        return "special"
    # Forecast-oriented day words → SPECIAL (not OBS)
    if any(token in text for token in ("demain", "après-demain", "apres-demain")):
        return "special"
    if metric == Metric.TEXTREMES or metric == Metric.SKY or metric == Metric.PHENOMENA:
        return "special"
    # Rain/wind with a calendar date → SPECIAL bulletin (not OBS quotidien)
    if metric in {Metric.RAIN, Metric.WIND} and date is not None:
        if not any(k in text for k in ("quotidien", "journalier", "horaire", "rr06", "rr12", "rr18")):
            return "special"
    if any(
        token in text
        for token in (
            "quotidien",
            "quotidienne",
            "journalier",
            "journalière",
            "journaliere",
            "obsmet-jour",
            "bulletin du jour",
        )
    ):
        return "daily"
    if "horaire" in text:
        return "hourly"
    if metric in DAILY_METRICS:
        return "daily"
    if date is not None and hour is None:
        return "daily"
    if hour is not None:
        return "hourly"
    return "auto"


def detect_intent(message: str) -> Intent:
    text = message.lower()
    scores: dict[Intent, int] = {intent: 0 for intent in Intent}

    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[intent] += 1

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        if any(token in text for token in ("il fait", "fait-il", "quel temps")):
            return Intent.CURRENT
        return Intent.UNKNOWN
    return best


def extract_hour(message: str) -> int | None:
    # "à midi" is daily T12, not an hourly clock slot
    if re.search(r"[àa]\s+midi|\bt12\b", message, re.IGNORECASE):
        if not HOUR_PATTERN.search(message):
            return None
    match = HOUR_PATTERN.search(message)
    if not match:
        lower = message.lower()
        if "minuit" in lower:
            return 0
        return None
    if match.group(1) is not None:
        hour = int(match.group(1))
    else:
        hour = int(match.group(3))
    if 0 <= hour <= 23:
        return hour
    return None


def extract_city(
    message: str,
    fallback: str | None = None,
    known_places: list[str] | None = None,
) -> str | None:
    text_norm = _normalize(message)

    if known_places:
        ranked = sorted(known_places, key=lambda name: len(_normalize(name)), reverse=True)
        for place in ranked:
            needle = _normalize(place)
            if needle and needle in text_norm:
                return place

    city_pattern = re.compile(
        r"(?:\b(?:à|a|auprès de|pour|sur|dans|de)\s+)([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']+(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']+){0,3})",
        re.IGNORECASE,
    )
    matches = city_pattern.findall(message.strip())
    for candidate in reversed(matches):
        cleaned = candidate.strip(" .,!?;:")
        if _normalize(cleaned) in STOPWORDS or len(cleaned) < 2:
            continue
        return cleaned
    return fallback


def extract_cities(
    message: str,
    known_places: list[str] | None = None,
) -> list[str]:
    """Return all known places mentioned in the message (longest match first)."""
    if not known_places:
        single = extract_city(message, known_places=known_places)
        return [single] if single else []

    text_norm = _normalize(message)
    ranked = sorted(known_places, key=lambda name: len(_normalize(name)), reverse=True)
    found: list[str] = []
    remaining = f" {text_norm} "
    for place in ranked:
        needle = _normalize(place)
        if not needle:
            continue
        token = f" {needle} "
        if token in remaining:
            found.append(place)
            remaining = remaining.replace(token, " ", 1)
    return found


def is_compare_query(message: str, cities: list[str]) -> bool:
    text = message.lower()
    if any(
        token in text
        for token in (
            "compare",
            "comparer",
            "comparaison",
            " versus ",
            " vs ",
            " vs.",
            "contre",
            "différence",
            "difference",
        )
    ):
        return len(cities) >= 2
    # "Rabat et Tanger" / "Rabat avec Kenitra"
    if len(cities) >= 2 and re.search(r"\b(et|avec|ou)\b", text):
        return True
    return False


FOLLOW_UP_PATTERNS = (
    r"^et\b",
    r"^pareil\b",
    r"^idem\b",
    r"^même\b",
    r"^meme\b",
    r"^aussi\b",
    r"et toi",
    r"et pour\b",
    r"pareil pour\b",
    r"same for\b",
)


def is_follow_up(message: str) -> bool:
    text = message.lower().strip()
    if len(text.split()) <= 6 and any(re.search(p, text) for p in FOLLOW_UP_PATTERNS):
        return True
    # Short metric-only or day-only turns
    if len(text.split()) <= 4 and (
        extract_metric(message) is not None or extract_day_filter(message) is not None
    ):
        # "demain", "le vent", "et demain ?"
        if extract_city(message) is None:
            return True
    return False


def apply_session_context(parsed: ParsedQuery, ctx) -> ParsedQuery:
    """Fill missing slots from previous turn for multi-turn memory."""
    if not is_follow_up(parsed.raw) and parsed.city and parsed.dataset != "auto":
        # Still inherit day/metric lightly when user only changes city via "pareil pour"
        pass

    follow = is_follow_up(parsed.raw)
    city = parsed.city
    cities = list(parsed.cities)
    metric = parsed.metric
    day_filter = parsed.day_filter
    date = parsed.date
    hour = parsed.hour
    dataset = parsed.dataset
    compare = parsed.compare

    if follow:
        if not cities and ctx.city:
            city = ctx.city
            cities = [ctx.city]
        if metric is None and ctx.metric is not None:
            metric = ctx.metric
        if day_filter is None and ctx.day_filter is not None:
            day_filter = ctx.day_filter
        if date is None and ctx.date is not None:
            date = ctx.date
        if hour is None and ctx.hour is not None and dataset in {"auto", "hourly"}:
            hour = ctx.hour
        if dataset == "auto" and ctx.dataset:
            dataset = ctx.dataset
        # "pareil pour Tanger" → keep metric/day, new city already in cities
        if cities and ctx.metric and metric is None:
            metric = ctx.metric
        if cities and ctx.day_filter and day_filter is None:
            day_filter = ctx.day_filter
        if dataset == "auto":
            if day_filter or metric in {
                Metric.TEXTREMES,
                Metric.SKY,
                Metric.PHENOMENA,
                Metric.RAIN,
                Metric.WIND,
            }:
                dataset = "special"

    # If user only says a new city with "et pour X" style already handled
    if follow and cities and len(cities) == 1:
        city = cities[0]

    out_cities = cities
    if follow and not out_cities and ctx.city:
        out_cities = [ctx.city]
    out_city = city or (ctx.city if follow else None) or parsed.city

    return ParsedQuery(
        intent=parsed.intent,
        city=out_city,
        hour=hour,
        date=date,
        metric=metric,
        dataset=dataset,
        day_filter=day_filter,
        cities=out_cities,
        compare=compare,
        raw=parsed.raw,
    )


def parse_message(
    message: str,
    default_city: str,
    known_places: list[str] | None = None,
) -> ParsedQuery:
    intent = detect_intent(message)
    cities = extract_cities(message, known_places=known_places)
    city = cities[0] if cities else extract_city(message, fallback=None, known_places=known_places)
    hour = extract_hour(message)
    date = extract_date(message)
    metric = extract_metric(message)
    dataset = detect_dataset(message, metric, hour, date)
    day_filter = extract_day_filter(message)
    compare = is_compare_query(message, cities)

    # Force intents from dataset keywords when clear
    if dataset == "bms":
        intent = Intent.ALERTS
    elif dataset == "special" or compare:
        intent = Intent.FORECAST if dataset != "bms" else intent
        if compare and dataset == "auto":
            dataset = "special"

    return ParsedQuery(
        intent=intent,
        city=city or default_city,
        hour=hour,
        date=date,
        metric=metric,
        dataset=dataset,
        day_filter=day_filter,
        cities=cities,
        compare=compare,
        raw=message,
    )
