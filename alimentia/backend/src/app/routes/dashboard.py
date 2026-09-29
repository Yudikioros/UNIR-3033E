"""Expone el resumen operativo de pacientes, consultas y planes."""
from fastapi import APIRouter, Request

from app.repositories.dashboard import get_dashboard_summary
from app.schemas.dashboard import DashboardSummary

router = APIRouter(prefix='/api/v1')


@router.get('/dashboard/summary', response_model=DashboardSummary)
async def dashboard_summary(request: Request):
    return await get_dashboard_summary(request.app.state.db)
