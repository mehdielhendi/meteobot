"""Build contextual follow-up suggestions after an answer."""

from __future__ import annotations

from app.services.intent import Metric


def build_suggestions(
    *,
    city: str | None,
    metric: Metric | None,
    dataset: str | None,
    day_filter: str | None,
    compare_cities: list[str] | None = None,
) -> list[str]:
    city = city or "Rabat"
    day = day_filter or "demain"
    day_q = day if day != "Aujourd'hui" else "aujourd'hui"
    if day == "Demain":
        day_q = "demain"
    if day == "Après-Demain":
        day_q = "après-demain"

    suggestions: list[str] = []

    if compare_cities and len(compare_cities) >= 2:
        a, b = compare_cities[0], compare_cities[1]
        suggestions = [
            f"Vent {a} vs {b} {day_q}",
            f"État du ciel {a} vs {b} {day_q}",
            f"Prévisions à {a} {day_q}",
        ]
        return suggestions[:3]

    if dataset in {"bms", "alerts"} or (dataset and "bms" in dataset):
        suggestions = [
            f"Prévisions à {city} demain",
            f"Températures extrêmes à {city} demain",
            "Où risque-t-il de pleuvoir dans le Nord demain ?",
        ]
        return suggestions[:3]

    if dataset in {"special", "special_compare", "scenario"}:
        if dataset == "scenario" or city.lower() in {"nord", "rif", "atlantique"}:
            suggestions = [
                "Alerte à Tanger",
                "Compare Rabat et Kenitra demain",
                "Températures extrêmes à Tetouan demain",
            ]
            return suggestions[:3]
        if metric == Metric.TEXTREMES:
            suggestions = [
                f"Vent prévu à {city} {day_q}",
                f"État du ciel à {city} {day_q}",
                f"Compare {city} et Tanger {day_q}",
            ]
        elif metric == Metric.WIND:
            suggestions = [
                f"Températures extrêmes à {city} {day_q}",
                f"Phénomènes à {city} {day_q}",
                f"Compare {city} et Rabat {day_q}",
            ]
        elif metric == Metric.RAIN:
            suggestions = [
                f"Phénomènes à {city} {day_q}",
                "Où risque-t-il de pleuvoir dans le Nord demain ?",
                f"Alerte à {city}",
            ]
        else:
            suggestions = [
                f"Températures extrêmes à {city} {day_q}",
                f"Vent prévu à {city} {day_q}",
                f"Compare {city} et Kenitra {day_q}",
            ]
        return suggestions[:3]

    if dataset in {"hourly", "daily"}:
        suggestions = [
            f"Prévisions à {city} demain",
            f"Alerte à {city}",
            f"Températures extrêmes à {city} demain",
        ]
        return suggestions[:3]

    return [
        f"Prévisions à {city} demain",
        "Compare Rabat et Tanger demain",
        "Où risque-t-il de pleuvoir dans le Nord demain ?",
    ]
