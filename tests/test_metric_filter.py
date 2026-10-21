from pathlib import Path

from app.services.intent import Metric, extract_metric, parse_message
from app.services.obs_store import ObsStore


def test_extract_metric_wind():
    assert extract_metric("Vent à Mdiq à 09h") == Metric.WIND


def test_extract_metric_humidity():
    assert extract_metric("Humidité à Mdiq à 09h") == Metric.HUMIDITY


def test_extract_metric_none_for_general():
    assert extract_metric("Météo à Mdiq à 09h") is None
    assert extract_metric("Observation Fnideq à 12h") is None


def test_format_metric_only_wind():
    store = ObsStore(Path("data/obs/hourly.json"))
    hit = store.get_observation("Mdiq", hour=9)
    assert hit is not None
    reply = store.format_observation(hit, metric=Metric.WIND)
    assert "Vent :" in reply
    assert "Température :" not in reply
    assert "Humidité :" not in reply
    assert "Pression :" not in reply
    assert "Source :" in reply


def test_format_metric_only_humidity():
    store = ObsStore(Path("data/obs/hourly.json"))
    hit = store.get_observation("Mdiq", hour=9)
    assert hit is not None
    reply = store.format_observation(hit, metric=Metric.HUMIDITY)
    assert "Humidité :" in reply
    assert "Vent :" not in reply
    assert "Température :" not in reply


def test_format_full_for_general():
    store = ObsStore(Path("data/obs/hourly.json"))
    hit = store.get_observation("Mdiq", hour=9)
    assert hit is not None
    reply = store.format_observation(hit, metric=None)
    assert "Température :" in reply
    assert "Humidité :" in reply


def test_parse_message_includes_metric():
    parsed = parse_message(
        "Vent à Mdiq à 09h",
        default_city="Rabat Ville",
        known_places=["Mdiq", "Rabat Ville"],
    )
    assert parsed.metric == Metric.WIND
    assert parsed.city == "Mdiq"
    assert parsed.hour == 9
