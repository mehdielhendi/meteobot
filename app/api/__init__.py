from fastapi import APIRouter, Request

from app.models import ChatRequest, ChatResponse, HealthResponse
from app.services.chatbot import ChatbotService
from app.services.dashboard import build_dashboard

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(status="ok", app=settings.app_name, env=settings.app_env)


@router.get("/dashboard")
async def dashboard(request: Request):
    """Ops summary: vigilance pins, ticker tape, metric cards."""
    return build_dashboard(
        bms=request.app.state.bms_store,
        obs=request.app.state.obs_store,
        daily=request.app.state.daily_store,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    chatbot: ChatbotService = request.app.state.chatbot
    return await chatbot.reply(
        payload.message,
        city_override=payload.city,
        session_id=payload.session_id,
    )


@router.get("/alerts/{place}")
async def alerts_for_place(place: str, request: Request):
    """Map click → BMS alert summary for a province/city."""
    chatbot: ChatbotService = request.app.state.chatbot
    response = await chatbot.reply(
        f"Alerte à {place}",
        city_override=place,
        session_id=None,
    )
    return response
