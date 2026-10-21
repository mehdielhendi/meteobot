from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Chatbot Météorologique"
    app_env: str = "development"
    debug: bool = True

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    weather_provider: str = "open-meteo"
    openweather_api_key: str = ""

    # Moroccan DRMNO observations (local PDFs ingested to JSON)
    obs_data_path: str = str(ROOT_DIR / "data" / "obs" / "hourly.json")
    obs_source_dir: str = r"sources/obs_horaire"
    obs_daily_data_path: str = str(ROOT_DIR / "data" / "obs" / "daily.json")
    obs_daily_source_dir: str = r"sources/obs_quotidienne"
    bms_data_path: str = str(ROOT_DIR / "data" / "obs" / "bms_alerts.json")
    special_data_path: str = str(ROOT_DIR / "data" / "obs" / "special_forecasts.json")
    pfa_source_dir: str = r"sources/bulletins"

    default_city: str = "Rabat"
    default_lat: float = 34.0209
    default_lon: float = -6.8416


@lru_cache
def get_settings() -> Settings:
    return Settings()
