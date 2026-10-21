from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Intent(str, Enum):
    CURRENT = "current"
    FORECAST = "forecast"
    ALERTS = "alerts"
    CLIMATE = "climate"
    HELP = "help"
    UNKNOWN = "unknown"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    city: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    intent: Intent
    city: str
    data: dict[str, Any] | None = None
    suggestions: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WeatherObservation(BaseModel):
    city: str
    temperature_c: float
    humidity_pct: float | None = None
    wind_speed_kmh: float | None = None
    weather_code: int | None = None
    description: str
    observed_at: datetime


class ForecastDay(BaseModel):
    date: str
    temp_max_c: float
    temp_min_c: float
    precipitation_mm: float | None = None
    description: str


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
