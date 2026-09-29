"""Expone el asistente contextual con el manejo de errores de captura."""
from fastapi import APIRouter, Request

from app.routes.capture import CaptureRoute
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.services.assistant_service import AlimentiaAssistantService

router = APIRouter(prefix="/api/v1", route_class=CaptureRoute)


@router.post("/assistant/chat", response_model=AssistantChatResponse)
async def assistant_chat(dto: AssistantChatRequest, request: Request):
    service = AlimentiaAssistantService()
    return await service.chat(request.app.state.db, dto)
