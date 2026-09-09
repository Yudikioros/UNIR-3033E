"""
Trazabilidad completa de un plan (Fase 6, Parte B).

Reconstruye cómo se produjo un DietPlan sin consultar manualmente múltiples
tablas: consulta -> cálculo -> ruleset -> base alimentaria -> conocimiento
recuperado -> generación IA -> validaciones -> intervención humana ->
aprobación/rechazo. Nunca expone prompts completos, secrets, API keys, rutas
internas, el UUID del paciente, ni PII no pertinente.
"""
from app.repositories.capture import CaptureError
from app.schemas.traceability import (
    PlanTraceabilityRead, TraceabilityCalculation, TraceabilityGeneration,
    TraceabilityHumanReview, TraceabilityPlan, TraceabilityResources,
    TraceabilitySource, TraceabilityValidation,
)
from app.services.food_db import FOOD_SOURCE_NAME, FOOD_SOURCE_VERSION

PLAN_INCLUDE = {
    "generationLinks": {"include": {"generation": {
        "include": {"retrievedSources": {"include": {"knowledgeSource": True}}}}}},
    "validations": True,
}


async def get_plan_traceability(db, plan_id: str) -> PlanTraceabilityRead:
    plan = await db.dietplan.find_unique(where={"id": plan_id}, include=PLAN_INCLUDE)
    if plan is None:
        raise CaptureError(404, "No se encontró el plan.")

    origin_link = next((link for link in plan.generationLinks or [] if link.isOrigin), None)
    generation = origin_link.generation if origin_link else None

    calculation_row = None
    calculations = await db.consultationcalculation.find_many(
        where={"consultationId": plan.consultationId}, include={"metrics": True})
    if calculations:
        calculation_row = sorted(calculations, key=lambda r: (r.recordedAt, r.id), reverse=True)[0]

    # Un guardado de edición puede generar varias filas (una por campo cambiado, ver
    # `plan_management.edit_plan`); todas comparten `changedAt`, así que se cuentan
    # timestamps distintos ("guardados"), no filas ("campos cambiados").
    edit_rows = await db.dietplanchangelog.find_many(
        where={"dietPlanId": plan_id, "changeType": "MANUAL_EDIT"})
    edit_count = len({row.changedAt for row in edit_rows})
    regen_count = await db.dietplanchangelog.count(
        where={"dietPlanId": plan_id, "changeType": "REGENERATION_REQUESTED"})

    sources = [
        TraceabilitySource(sourceId=retrieved.knowledgeSource.id, name=retrieved.knowledgeSource.documentName,
            version=retrieved.knowledgeSource.version, document=retrieved.knowledgeSource.originalFilename)
        for retrieved in (generation.retrievedSources if generation else []) or []
    ]

    food_used = generation.foodDatabaseUsed if generation else None
    knowledge_used = generation.knowledgeBaseUsed if generation else None

    return PlanTraceabilityRead(
        plan=TraceabilityPlan(id=plan.id, version=plan.version, status=plan.status),
        calculation=TraceabilityCalculation(
            calculationId=calculation_row.id if calculation_row else None,
            method=calculation_row.calculationMethod if calculation_row else None,
            rulesetVersion=calculation_row.calculationRuleVersion if calculation_row else None,
            recordedAt=calculation_row.recordedAt if calculation_row else None,
        ),
        generation=TraceabilityGeneration(
            generationId=generation.id if generation else None,
            modelProvider=generation.modelProvider if generation else None,
            modelName=generation.modelName if generation else None,
            promptVersion=generation.promptVersion if generation else None,
            generationDurationMs=generation.executionTimeMs if generation else None,
            knowledgeBaseVersion=generation.knowledgeBaseVersion if generation else None,
        ),
        resources=TraceabilityResources(
            foodDatabaseUsed=food_used,
            foodDatabaseName=FOOD_SOURCE_NAME if food_used else None,
            foodDatabaseVersion=FOOD_SOURCE_VERSION if food_used else None,
            knowledgeBaseUsed=knowledge_used,
        ),
        sources=sources,
        humanReview=TraceabilityHumanReview(
            manualEditCount=edit_count, regenerationCount=regen_count,
            approvedAt=plan.approvedAt, approvedBy=plan.approvedBy,
            rejectedAt=plan.rejectedAt, rejectedBy=plan.rejectedBy,
        ),
        validations=[TraceabilityValidation(code=v.code, severity=v.severity, isBlocking=v.isBlocking, message=v.message)
                     for v in plan.validations or []],
    )
