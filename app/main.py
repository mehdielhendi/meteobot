from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import get_settings
from app.services.bms_store import BmsStore
from app.services.chatbot import ChatbotService
from app.services.obs_daily_store import DailyObsStore
from app.services.obs_store import ObsStore
from app.services.special_store import SpecialStore
from app.services.weather import WeatherService

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

    weather = WeatherService(settings)
    obs_store = ObsStore(Path(settings.obs_data_path))
    daily_store = DailyObsStore(Path(settings.obs_daily_data_path))
    bms_store = BmsStore(Path(settings.bms_data_path))
    special_store = SpecialStore(Path(settings.special_data_path))
    chatbot = ChatbotService(
        settings,
        weather,
        obs_store,
        daily_store,
        bms_store,
        special_store,
    )

    app.state.settings = settings
    app.state.weather = weather
    app.state.obs_store = obs_store
    app.state.daily_store = daily_store
    app.state.bms_store = bms_store
    app.state.special_store = special_store
    app.state.chatbot = chatbot

    app.include_router(router, prefix="/api")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
