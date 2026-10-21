import asyncio
from pathlib import Path

from app.config import Settings
from app.models import Intent
from app.services.bms_store import BmsStore
from app.services.chatbot import ChatbotService
from app.services.intent import Metric, apply_session_context, is_follow_up, parse_message
from app.services.obs_daily_store import DailyObsStore
from app.services.obs_store import ObsStore
from app.services.scenarios import is_scenario_query, run_rain_scenario
from app.services.session import SessionContext
from app.services.special_store import SpecialStore
from app.services.suggestions import build_suggestions
from app.services.weather import WeatherService


def _bot() -> ChatbotService:
    settings = Settings()
    return ChatbotService(
        settings=settings,
        weather=WeatherService(settings),
        obs_store=ObsStore(Path("data/obs/hourly.json")),
        daily_store=DailyObsStore(Path("data/obs/daily.json")),
        bms_store=BmsStore(Path("data/obs/bms_alerts.json")),
        special_store=SpecialStore(Path("data/obs/special_forecasts.json")),
    )


def test_is_follow_up_patterns():
    assert is_follow_up("et le vent ?")
    assert is_follow_up("pareil pour Tanger")
    assert is_follow_up("demain")
    assert not is_follow_up("Températures extrêmes à Kenitra demain")


def test_apply_session_keeps_city_and_day():
    known = ["Kenitra", "Tanger", "Rabat"]
    first = parse_message(
        "Températures extrêmes à Kenitra demain",
        default_city="Rabat",
        known_places=known,
    )
    ctx = SessionContext(
        city="Kenitra",
        metric=Metric.TEXTREMES,
        dataset="special",
        day_filter="Demain",
    )
    follow = parse_message("et le vent ?", default_city="Rabat", known_places=known)
    merged = apply_session_context(follow, ctx)
    assert merged.city == "Kenitra"
    assert merged.metric == Metric.WIND
    assert merged.day_filter == "Demain"
    assert merged.dataset == "special"
    assert first.metric == Metric.TEXTREMES


def test_pareil_pour_city_switch():
    known = ["Kenitra", "Tanger", "Rabat"]
    ctx = SessionContext(
        city="Kenitra",
        metric=Metric.TEXTREMES,
        dataset="special",
        day_filter="Demain",
    )
    follow = parse_message("pareil pour Tanger", default_city="Rabat", known_places=known)
    merged = apply_session_context(follow, ctx)
    assert merged.city == "Tanger"
    assert merged.metric == Metric.TEXTREMES
    assert merged.day_filter == "Demain"


def test_scenario_query_detection():
    assert is_scenario_query("Où risque-t-il de pleuvoir dans le Nord demain ?")
    assert is_scenario_query("Quelles villes du Rif ont un risque d'alerte ?")


def test_rain_scenario_runs():
    special = SpecialStore(Path("data/obs/special_forecasts.json"))
    reply = run_rain_scenario(special, "nord", "Demain", None, Metric.RAIN)
    assert "Scénario" in reply
    assert "Source :" in reply


def test_suggestions_non_empty():
    tips = build_suggestions(
        city="Kenitra",
        metric=Metric.TEXTREMES,
        dataset="special",
        day_filter="Demain",
    )
    assert len(tips) == 3
    assert any("vent" in t.lower() for t in tips)


def test_session_memory_end_to_end():
    bot = _bot()

    async def run():
        first = await bot.reply(
            "Températures extrêmes à Kenitra demain",
            session_id="test-session-1",
        )
        assert first.intent == Intent.FORECAST
        assert "Kenitra" in first.reply or "Kénitra" in first.reply
        assert first.suggestions

        second = await bot.reply("et le vent ?", session_id="test-session-1")
        assert "vent" in second.reply.lower() or "Vent" in second.reply
        assert "Kenitra" in second.city or "Kenitra" in second.reply

        third = await bot.reply("pareil pour Tanger", session_id="test-session-1")
        assert "Tanger" in third.city or "Tanger" in third.reply

        scenario = await bot.reply(
            "Où risque-t-il de pleuvoir dans le Nord demain ?",
            session_id="test-session-1",
        )
        assert scenario.suggestions
        assert "Scénario" in scenario.reply or "région" in scenario.reply.lower() or "surveiller" in scenario.reply.lower()

        alert = await bot.reply("Alerte à Tetouan", session_id="test-map")
        assert alert.suggestions
        assert alert.intent == Intent.ALERTS or "vigilance" in alert.reply.lower() or "BMS" in alert.reply or "alerte" in alert.reply.lower()

    asyncio.run(run())
