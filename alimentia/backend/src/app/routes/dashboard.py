"""Resumen operativo (`/`). Aislado del resto de rutas igual que capture.py,
para poder probarse sin depender de Qdrant/Ollama en ejecución."""
from fastapi import APIRouter, Request

from app.repositories.dashboard import get_dashboard_summary
from app.schemas.dashboard import DashboardSummary

router = APIRouter(prefix='/api/v1')


@router.get('/dashboard/summary', response_model=DashboardSummary)
async def dashboard_summary(request: Request):
    return await get_dashboard_summary(request.app.state.db)
