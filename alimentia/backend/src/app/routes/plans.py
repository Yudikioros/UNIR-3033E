"""Rutas de ciclo de vida del plan (Fase 5): consulta, edición, aprobación, rechazo, regeneración.

Fase 6 agrega trazabilidad, métricas de evaluación y exportación a PDF sobre
el mismo plan, reutilizando `CaptureRoute` (capture.py) para mantener un
único vocabulario de errores (404/409/422/502/503) en toda la API.
"""
from fastapi import APIRouter, Request, Response

from app.repositories import evaluation_metrics, plan_management as repo, plan_traceability
from app.repositories.capture import CaptureError, get_consultation
from app.repositories.normalized import consultation_read
from app.routes.capture import CaptureRoute
from app.schemas.evaluation import EvaluationMetricsRead
from app.schemas.generation import DietPlanGenerationResponse, GenerationJobStarted
from app.schemas.plan_management import ApprovalRequest, DietPlanDetail, DietPlanEditRequest, RegenerateRequest, RejectionRequest
from app.schemas.traceability import PlanTraceabilityRead
from app.services.pdf_export import build_plan_pdf

router = APIRouter(prefix='/api/v1', route_class=CaptureRoute)


@router.get('/plans/{plan_id}', response_model=DietPlanDetail)
async def get_plan(plan_id: str, request: Request):
    return await repo.get_plan_detail(request.app.state.db, plan_id)


@router.get('/consultations/{consultation_id}/plans', response_model=list[DietPlanDetail])
async def consultation_plans(consultation_id: str, request: Request):
    return await repo.list_consultation_plans(request.app.state.db, consultation_id)


@router.patch('/plans/{plan_id}', response_model=DietPlanDetail)
async def edit_plan(plan_id: str, dto: DietPlanEditRequest, request: Request):
    return await repo.edit_plan(request.app.state.db, plan_id, dto)


@router.post('/plans/{plan_id}/approve', response_model=DietPlanDetail)
async def approve_plan(plan_id: str, dto: ApprovalRequest, request: Request):
    return await repo.approve_plan(request.app.state.db, plan_id, dto)


@router.post('/plans/{plan_id}/reject', response_model=DietPlanDetail)
async def reject_plan(plan_id: str, dto: RejectionRequest, request: Request):
    return await repo.reject_plan(request.app.state.db, plan_id, dto)


@router.post('/plans/{plan_id}/regenerate', response_model=DietPlanGenerationResponse)
async def regenerate_plan(plan_id: str, dto: RegenerateRequest, request: Request):
    return await repo.regenerate_plan(request.app.state.db, plan_id, dto)


@router.post('/plans/{plan_id}/regenerate/start', response_model=GenerationJobStarted)
async def start_regenerate_plan(plan_id: str, dto: RegenerateRequest, request: Request):
    """Corrección de UX (progreso por etapas real): responde de inmediato con
    el id de la generación en curso; el frontend hace polling de
    /generations/{id}/status en vez de esperar bloqueado la respuesta."""
    generation_id = await repo.start_regeneration_job(request.app.state.db, plan_id, dto)
    return GenerationJobStarted(generationId=generation_id)


@router.get('/plans/{plan_id}/traceability', response_model=PlanTraceabilityRead)
async def plan_traceability_route(plan_id: str, request: Request):
    return await plan_traceability.get_plan_traceability(request.app.state.db, plan_id)


@router.get('/plans/{plan_id}/evaluation-metrics', response_model=EvaluationMetricsRead)
async def plan_evaluation_metrics_route(plan_id: str, request: Request):
    return await evaluation_metrics.get_evaluation_metrics(request.app.state.db, plan_id)


@router.get('/plans/{plan_id}/export/pdf')
async def export_plan_pdf(plan_id: str, request: Request):
    db = request.app.state.db
    plan = await repo.get_plan_detail(db, plan_id)
    if plan.status != 'APPROVED':
        raise CaptureError(409, 'Solo un plan APROBADO puede exportarse como documento final.')

    consultation = await get_consultation(db, plan.consultationId)
    targets = consultation_read(consultation)
    pdf_bytes = build_plan_pdf(plan=plan, consultation=targets,
        patient_name=consultation.patient.name, sources=plan.sources)

    filename = f'plan-{plan.id}-v{plan.version}.pdf'
    return Response(content=pdf_bytes, media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'})
