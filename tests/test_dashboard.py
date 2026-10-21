from pathlib import Path

from app.services.bms_store import BmsStore
from app.services.dashboard import build_dashboard
from app.services.obs_daily_store import DailyObsStore
from app.services.obs_store import ObsStore


def test_ouazzane_alias_matches_latest_bms():
    bms = BmsStore(Path("data/obs/bms_alerts.json"))
    info = bms.level_for_place("Ouazzane")
    assert info["level"] == "orange"
    assert info["active"] is True


def test_dashboard_payload():
    payload = build_dashboard(
        bms=BmsStore(Path("data/obs/bms_alerts.json")),
        obs=ObsStore(Path("data/obs/hourly.json")),
        daily=DailyObsStore(Path("data/obs/daily.json")),
    )
    assert "places" in payload
    assert "metrics" in payload
    assert "ticker" in payload
    assert payload["places"]["Ouazzane"]["level"] == "orange"
    assert payload["metrics"]["active_alerts"] >= 1
    assert payload["ticker"]
