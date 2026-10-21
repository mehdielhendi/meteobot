from pathlib import Path

from app.models import Intent
from app.services.intent import Metric, parse_message
from app.services.special_store import SpecialStore


def test_compare_intent_extracts_two_cities():
    parsed = parse_message(
        "Compare Rabat et Tanger demain",
        default_city="Rabat",
        known_places=["Rabat", "Tanger", "Kenitra"],
    )
    assert parsed.compare is True
    assert parsed.cities[:2] == ["Rabat", "Tanger"] or set(parsed.cities[:2]) == {
        "Rabat",
        "Tanger",
    }
    assert parsed.day_filter == "Demain"
    assert parsed.dataset == "special"


def test_compare_vs_extremes():
    parsed = parse_message(
        "Températures extrêmes Kenitra vs Al Hoceima demain",
        default_city="Rabat",
        known_places=["Kenitra", "Al-Hoceima", "Al Houceima", "Rabat"],
    )
    assert parsed.compare is True
    assert parsed.metric == Metric.TEXTREMES
    assert len(parsed.cities) >= 2


def test_special_format_compare():
    store = SpecialStore(Path("data/obs/special_forecasts.json"))
    reply = store.format_compare(
        "Rabat",
        "Kenitra",
        metric=Metric.TEXTREMES,
        day_filter="Demain",
    )
    assert reply is not None
    assert "Comparaison SPECIAL" in reply
    assert "Rabat" in reply
    assert "Kenitra" in reply
    assert "Températures" not in reply or ":" in reply
    assert "Source :" in reply
