"""
Servicio de métricas de evaluación por caso (Fase 6, Parte C).

Todo se deriva de datos ya persistidos (AIGeneration, DietPlan,
DietPlanChangeLog, PlanValidation, PlanNutrientObservation,
ConsultationCalculation, RetrievedSource): no se crea ninguna tabla nueva.
Nunca inventa métricas experimentales -ver sección 19 de Fase 6-.
"""
from app.repositories.capture import CaptureError
from app.schemas.evaluation import EvaluationMetricsRead

CASE_PLAN_INCLUDE = {
    "meals": True,
    "validations": True,
    "nutrientObservations": True,
    "generationLinks": {"include": {"generation": {"include": {"retrievedSources": True}}}},
}


def _origin_generation(plan):
    link = next((link for link in plan.generationLinks or [] if link.isOrigin), None)
    return link.generation if link else None


def _total_calories(plan):
    for observation in plan.nutrientObservations or []:
        if observation.metricCode == "totalCalories":
            return observation.value
    return None


def _blocking_count(plan):
    return sum(1 for v in plan.validations or [] if v.isBlocking)


def _energy_deviation_percent(plan, target_calories):
    total = _total_calories(plan)
    if total is None or not target_calories:
        return None
    return round((total - target_calories) / target_calories * 100, 2)


async def get_evaluation_metrics(db, plan_id: str) -> EvaluationMetricsRead:
    anchor = await db.dietplan.find_unique(where={"id": plan_id})
    if anchor is None:
        raise CaptureError(404, "No se encontró el plan.")

    consultation_id = anchor.consultationId
    plans = await db.dietplan.find_many(
        where={"consultationId": consultation_id}, include=CASE_PLAN_INCLUDE, order={"version": "asc"})
    if not plans:
        raise CaptureError(404, "No se encontró el plan.")

    calculations = await db.consultationcalculation.find_many(
        where={"consultationId": consultation_id}, include={"metrics": True})
    latest_calc = None
    if calculations:
        latest_calc = sorted(calculations, key=lambda r: (r.recordedAt, r.id), reverse=True)[0]
    target_calories = None
    if latest_calc:
        target_calories = next((m.value for m in latest_calc.metrics or [] if m.metricCode == "targetCalories"), None)

    initial_plan = plans[0]
    final_plan = plans[-1]
    approved_plan = next((p for p in plans if p.status == "APPROVED"), None)

    generation_count = await db.aigeneration.count(
        where={"consultationId": consultation_id, "status": "SUCCESS"})
    # Un guardado de edición puede generar varias filas (una por campo cambiado, ver
    # `plan_management.edit_plan`); todas comparten `changedAt`, así que se cuentan
    # timestamps distintos ("guardados"), no filas ("campos cambiados").
    edit_rows = await db.dietplanchangelog.find_many(
        where={"dietPlanId": {"in": [p.id for p in plans]}, "changeType": "MANUAL_EDIT"})
    manual_edit_count = len({row.changedAt for row in edit_rows})
    regeneration_count = await db.dietplanchangelog.count(
        where={"dietPlanId": {"in": [p.id for p in plans]}, "changeType": "REGENERATION_REQUESTED"})

    final_generation = _origin_generation(final_plan)
    initial_generation = _origin_generation(initial_plan)

    time_to_approval = None
    if approved_plan and approved_plan.approvedAt and initial_generation and initial_generation.createdAt:
        time_to_approval = (approved_plan.approvedAt - initial_generation.createdAt).total_seconds()

    return EvaluationMetricsRead(
        consultationId=consultation_id, planId=plan_id,
        generationCount=generation_count, regenerationCount=regeneration_count,
        manualEditCount=manual_edit_count, versionCount=len(plans),
        initialPlanVersion=initial_plan.version, finalPlanVersion=final_plan.version,
        approvedVersion=approved_plan.version if approved_plan else None,
        generationDurationMs=final_generation.executionTimeMs if final_generation else None,
        timeFromFirstGenerationToApprovalSeconds=time_to_approval,
        initialEnergyDeviationPercent=_energy_deviation_percent(initial_plan, target_calories),
        finalEnergyDeviationPercent=_energy_deviation_percent(final_plan, target_calories),
        initialBlockingValidationCount=_blocking_count(initial_plan),
        finalBlockingValidationCount=_blocking_count(final_plan),
        initialMealCount=len(initial_plan.meals or []),
        finalMealCount=len(final_plan.meals or []),
        knowledgeBaseUsed=final_generation.knowledgeBaseUsed if final_generation else None,
        foodDatabaseUsed=final_generation.foodDatabaseUsed if final_generation else None,
        retrievedSourceCount=len(final_generation.retrievedSources or []) if final_generation else 0,
        modelName=final_generation.modelName if final_generation else None,
        promptVersion=final_generation.promptVersion if final_generation else None,
        calculationRuleVersion=latest_calc.calculationRuleVersion if latest_calc else None,
    )
