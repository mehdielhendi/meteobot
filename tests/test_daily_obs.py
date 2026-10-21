from pathlib import Path

from app.services.intent import Metric, extract_metric, parse_message
from app.services.obs_daily_store import DailyObsStore


def test_extract_tn_tx_t12():
    assert extract_metric("TN à Tanger") == Metric.TN
    assert extract_metric("Température maximale à Larache") == Metric.TX
    assert extract_metric("T12 à Rabat") == Metric.T12
    assert extract_metric("Température à midi à Kenitra") == Metric.T12


def test_extract_rr_hu():
    assert extract_metric("RR06 à Kenitra") == Metric.RR06
    assert extract_metric("Humidité de 06 à Chefchaouen") == Metric.HU06


def test_daily_format_metric_only():
    store = DailyObsStore(Path("data/obs/daily.json"))
    hit = store.get_observation("Tanger", date="2026-06-10")
    assert hit is not None
    reply = store.format_observation(hit, metric=Metric.TN)
    assert "TN (température minimale)" in reply
    assert "TX" not in reply
    assert "Source :" in reply


def test_parse_daily_query():
    parsed = parse_message(
        "TN à Tanger le 10/06/2026",
        default_city="Rabat",
        known_places=["Tanger", "Rabat"],
    )
    assert parsed.metric == Metric.TN
    assert parsed.dataset == "daily"
    assert parsed.date == "2026-06-10"
    assert parsed.city == "Tanger"
