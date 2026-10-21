from pathlib import Path

from app.models import Intent
from app.services.bms_store import BmsStore
from app.services.intent import Metric, extract_metric, parse_message
from app.services.special_store import SpecialStore


def test_bms_place_filter():
    store = BmsStore(Path("data/obs/bms_alerts.json"))
    hits = store.find_for_place("Tetouan", "2026-01-27")
    assert hits
    assert any(h.get("vigilance_level") for h in hits)


def test_special_rabat_forecast():
    store = SpecialStore(Path("data/obs/special_forecasts.json"))
    forecast = store.get_forecast("Rabat", "2026-01-27")
    assert forecast is not None
    reply = store.format_forecast(forecast, day_filter="Demain")
    assert "Demain" in reply
    assert "Après-Demain" not in reply


def test_parse_bms_intent():
    parsed = parse_message("Alerte à Tetouan", default_city="Rabat")
    assert parsed.intent == Intent.ALERTS
    assert parsed.dataset == "bms"


def test_parse_special_intent():
    parsed = parse_message(
        "Prévisions à Rabat demain",
        default_city="Rabat",
        known_places=["Rabat", "Tanger"],
    )
    assert parsed.intent == Intent.FORECAST
    assert parsed.dataset == "special"
    assert parsed.day_filter == "Demain"
    assert parsed.city == "Rabat"


def test_temperatures_extremes_routes_to_special():
    parsed = parse_message(
        "Températures extrêmes a kénitra demain",
        default_city="Rabat",
        known_places=["Kenitra", "Rabat"],
    )
    assert parsed.metric == Metric.TEXTREMES
    assert parsed.dataset == "special"
    assert parsed.intent == Intent.FORECAST
    assert parsed.day_filter == "Demain"
    assert parsed.city == "Kenitra"


def test_al_hoceima_spelling_variants():
    store = SpecialStore(Path("data/obs/special_forecasts.json"))
    for q in ["al hoceima", "Al-Hoceima", "Al Hoceima", "Al Houceima"]:
        assert store.match_city(q) == "Al Houceima", q
    forecast = store.get_forecast("al hoceima")
    assert forecast is not None
    assert forecast["city"] == "Al Houceima"


def test_special_field_only_filters():
    assert extract_metric("État du ciel à Rabat demain") == Metric.SKY
    assert extract_metric("Phénomènes à Tanger demain") == Metric.PHENOMENA
    assert extract_metric("Vitesse du vent à Larache demain") == Metric.WIND

    store = SpecialStore(Path("data/obs/special_forecasts.json"))
    forecast = store.get_forecast("Rabat")
    assert forecast is not None
    sky = store.format_forecast(forecast, metric=Metric.SKY, day_filter="Demain")
    assert "État du ciel" in sky
    assert "Vent :" not in sky
    assert "Phénomènes :" not in sky
    assert "Températures extrêmes" not in sky
