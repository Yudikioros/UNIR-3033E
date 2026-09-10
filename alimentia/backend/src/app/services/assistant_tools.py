"""
Herramientas READ-ONLY del asistente IA contextual (sección 8).

Cada herramienta valida sus parámetros, reutiliza los repositorios ya
existentes de Fase 1-6 (nunca duplica su lógica ni ejecuta SQL propio salvo
las agregaciones nuevas en `repositories/assistant.py`), y devuelve un DTO
minimizado (sección 19) o levanta `ToolError` si el recurso no existe o el
parámetro es inválido -nunca inventa un resultado-.
"""
import json

from app.repositories import assistant as assistant_repo
from app.repositories.capture import CaptureError, get_consultation, get_patient, patient_projection
from app.repositories.knowledge import list_sources
from app.repositories.plan_management import get_plan_detail, list_consultation_plans
from app.repositories.normalized import consultation_read
from app.schemas.assistant import (
    AssistantCalculationDetail, AssistantConsultationSummary, AssistantFood, AssistantKnowledgeChunk,
    AssistantKnowledgeSourceRef, AssistantMeal, AssistantPatientRef, AssistantPatientSummary,
    AssistantPlanDetail, AssistantPlanSummary, AssistantSourceRef, AssistantValidation,
    PatientPlanStatusRef, PlanStatusCount, PlanVersionComparison,
)
from app.services import rag_engine


class ToolError(Exception):
    """Parámetro inválido o recurso inexistente: nunca se convierte en un
    resultado inventado, se informa como tal al modelo (sección 38)."""


def _require(value: str | None, field: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ToolError(f"El parámetro '{field}' es obligatorio.")
    return value


async def _plan_to_detail(db, plan_id: str) -> AssistantPlanDetail:
    try:
        plan = await get_plan_detail(db, plan_id)
    except CaptureError:
        raise ToolError(f"No se encontró ningún plan con id '{plan_id}'.") from None
    return AssistantPlanDetail(
        id=plan.id, consultationId=plan.consultationId, version=plan.version, status=plan.status,
        isEditable=plan.isEditable, createdAt=plan.createdAt,
        totalCalories=plan.totalCalories, targetCalories=plan.targetCalories,
        proteinGrams=plan.proteinGrams, carbohydrateGrams=plan.carbohydrateGrams, fatGrams=plan.fatGrams,
        fiberGrams=plan.fiberGrams, waterLiters=plan.waterLiters,
        blockingValidationCount=plan.blockingValidationCount,
        approvedAt=plan.approvedAt, approvedBy=plan.approvedBy, rejectedAt=plan.rejectedAt,
        rejectedBy=plan.rejectedBy, rejectionReason=plan.rejectionReason,
        meals=[AssistantMeal(mealType=meal.mealType, name=meal.name, foods=[
            AssistantFood(foodName=food.foodName, quantity=food.quantity, unit=food.unit,
                calories=food.calories, protein=food.protein, carbohydrates=food.carbohydrates,
                fat=food.fat, smaeEquivalent=food.smaeEquivalent) for food in meal.foods])
            for meal in plan.meals],
        validations=[AssistantValidation(code=v.code, severity=v.severity, message=v.message, isBlocking=v.isBlocking)
                     for v in plan.validations],
        sources=[AssistantSourceRef(knowledgeSourceId=s.knowledgeSourceId, documentName=s.documentName,
                    institution=s.institution, section=s.section) for s in plan.sources],
    )


async def get_patient_tool(db, patient_id: str) -> AssistantPatientSummary:
    patient_id = _require(patient_id, "patient_id")
    try:
        patient = await get_patient(db, patient_id)
    except CaptureError:
        raise ToolError(f"No se encontró ningún paciente con id '{patient_id}'.") from None
    projected = patient_projection(patient)
    return AssistantPatientSummary(id=projected.id, name=projected.name, sex=patient.sex,
        currentAge=projected.currentAge, defaultGoal=projected.defaultGoal, conditions=projected.conditions)


async def search_patients_tool(db, query: str) -> list[AssistantPatientRef]:
    query = _require(query, "query")
    matches = await assistant_repo.search_patients_by_name(db, query)
    return [AssistantPatientRef(id=row.id, name=row.name) for row in matches]


async def get_patient_consultations_tool(db, patient_id: str) -> list[AssistantConsultationSummary]:
    patient_id = _require(patient_id, "patient_id")
    try:
        patient = await get_patient(db, patient_id)
    except CaptureError:
        raise ToolError(f"No se encontró ningún paciente con id '{patient_id}'.") from None
    results = []
    for consultation in patient.consultations or []:
        full = await get_consultation(db, consultation.id)
        results.append(_consultation_summary(full))
    return results


def _consultation_summary(consultation) -> AssistantConsultationSummary:
    projected = consultation_read(consultation)
    return AssistantConsultationSummary(
        id=projected.id, patientId=projected.patientId, consultationDate=projected.consultationDate,
        status=consultation.status, goal=projected.goal, activityLevel=projected.activityLevel,
        weightKg=projected.weightKg, heightM=projected.heightM, targetCalories=projected.targetCalories,
        proteinGrams=projected.proteinGrams, carbohydrateGrams=projected.carbohydrateGrams,
        fatGrams=projected.fatGrams, fiberGrams=projected.fiberGrams, waterLiters=projected.waterLiters,
        calculationMethod=projected.calculationMethod, calculationRuleVersion=projected.calculationRuleVersion,
    )


async def get_consultation_tool(db, consultation_id: str) -> AssistantConsultationSummary:
    consultation_id = _require(consultation_id, "consultation_id")
    try:
        consultation = await get_consultation(db, consultation_id)
    except CaptureError:
        raise ToolError(f"No se encontró ninguna consulta con id '{consultation_id}'.") from None
    return _consultation_summary(consultation)


async def get_consultation_calculation_tool(db, consultation_id: str) -> AssistantCalculationDetail:
    consultation_id = _require(consultation_id, "consultation_id")
    try:
        consultation = await get_consultation(db, consultation_id)
    except CaptureError:
        raise ToolError(f"No se encontró ninguna consulta con id '{consultation_id}'.") from None
    projected = consultation_read(consultation)
    if projected.calculationMethod is None:
        raise ToolError("Esta consulta todavía no tiene un cálculo nutricional registrado.")
    details = {}
    if projected.calculationDetails:
        try:
            details = json.loads(projected.calculationDetails)
        except (ValueError, TypeError):
            details = {}
    return AssistantCalculationDetail(
        consultationId=consultation_id, calculationMethod=projected.calculationMethod,
        calculationRuleVersion=projected.calculationRuleVersion,
        recordedAt=None,
        bmi=projected.bmi, basalMetabolicRate=projected.basalMetabolicRate,
        activityFactor=details.get("activityFactor"), totalEnergyExpenditure=projected.totalEnergyExpenditure,
        goalAdjustmentKcal=details.get("goalAdjustmentKcal"), targetCalories=projected.targetCalories,
        macroDistributionPercentage=details.get("macroDistributionPercentage"),
        proteinGrams=projected.proteinGrams, carbohydrateGrams=projected.carbohydrateGrams,
        fatGrams=projected.fatGrams, fiberGrams=projected.fiberGrams, waterLiters=projected.waterLiters,
    )


async def get_patient_plans_tool(db, patient_id: str) -> list[AssistantPlanSummary]:
    patient_id = _require(patient_id, "patient_id")
    try:
        patient = await get_patient(db, patient_id)
    except CaptureError:
        raise ToolError(f"No se encontró ningún paciente con id '{patient_id}'.") from None
    results = []
    for consultation in patient.consultations or []:
        if not consultation.plans:
            continue
        plans = await list_consultation_plans(db, consultation.id)
        results.extend(AssistantPlanSummary(id=p.id, consultationId=p.consultationId, version=p.version,
            status=p.status, totalCalories=p.totalCalories, createdAt=p.createdAt,
            approvedAt=p.approvedAt, rejectedAt=p.rejectedAt) for p in plans)
    return results


async def get_consultation_plans_tool(db, consultation_id: str) -> list[AssistantPlanSummary]:
    consultation_id = _require(consultation_id, "consultation_id")
    try:
        plans = await list_consultation_plans(db, consultation_id)
    except CaptureError:
        raise ToolError(f"No se encontró ninguna consulta con id '{consultation_id}'.") from None
    return [AssistantPlanSummary(id=p.id, consultationId=p.consultationId, version=p.version, status=p.status,
        totalCalories=p.totalCalories, createdAt=p.createdAt, approvedAt=p.approvedAt, rejectedAt=p.rejectedAt)
        for p in plans]


async def get_plan_tool(db, plan_id: str) -> AssistantPlanDetail:
    plan_id = _require(plan_id, "plan_id")
    return await _plan_to_detail(db, plan_id)


async def get_plan_validations_tool(db, plan_id: str) -> list[AssistantValidation]:
    plan = await get_plan_tool(db, plan_id)
    return plan.validations


async def get_plan_sources_tool(db, plan_id: str) -> list[AssistantSourceRef]:
    plan = await get_plan_tool(db, plan_id)
    return plan.sources


async def compare_plan_versions_tool(db, plan_id_a: str, plan_id_b: str) -> PlanVersionComparison:
    plan_id_a = _require(plan_id_a, "plan_id_a")
    plan_id_b = _require(plan_id_b, "plan_id_b")
    a = await _plan_to_detail(db, plan_id_a)
    b = await _plan_to_detail(db, plan_id_b)

    foods_a = {food.foodName for meal in a.meals for food in meal.foods}
    foods_b = {food.foodName for meal in b.meals for food in meal.foods}
    quantities_a = {food.foodName: food.quantity for meal in a.meals for food in meal.foods}
    quantities_b = {food.foodName: food.quantity for meal in b.meals for food in meal.foods}
    quantity_changes = [
        {"foodName": name, "before": quantities_a[name], "after": quantities_b[name]}
        for name in (foods_a & foods_b) if quantities_a[name] != quantities_b[name]
    ]

    def _summary(detail: AssistantPlanDetail) -> AssistantPlanSummary:
        return AssistantPlanSummary(id=detail.id, consultationId=detail.consultationId, version=detail.version,
            status=detail.status, totalCalories=detail.totalCalories, createdAt=detail.createdAt,
            approvedAt=detail.approvedAt, rejectedAt=detail.rejectedAt)

    return PlanVersionComparison(
        planA=_summary(a), planB=_summary(b),
        statusChanged=a.status != b.status,
        totalCaloriesDelta=(b.totalCalories - a.totalCalories) if (a.totalCalories is not None and b.totalCalories is not None) else None,
        mealCountA=len(a.meals), mealCountB=len(b.meals),
        foodsAdded=sorted(foods_b - foods_a), foodsRemoved=sorted(foods_a - foods_b),
        quantityChanges=quantity_changes,
        validationsA=a.validations, validationsB=b.validations,
    )


async def search_knowledge_tool(db, query: str) -> list[AssistantKnowledgeChunk]:
    query = _require(query, "query")
    chunks = rag_engine.knowledge_base_service.search(query, top_k=3)
    return [AssistantKnowledgeChunk(sourceId=chunk.sourceId, documentName=chunk.documentName,
        institution=chunk.institution, version=chunk.version, content=chunk.content[:800]) for chunk in chunks]


async def list_knowledge_sources_tool(db) -> list[AssistantKnowledgeSourceRef]:
    sources = await list_sources(db)
    return [AssistantKnowledgeSourceRef(id=s.id, documentName=s.documentName, institution=s.institution,
        version=s.version, sourceType=s.sourceType, isActive=s.isActive) for s in sources]


async def count_plans_by_status_tool(db) -> list[PlanStatusCount]:
    rows = await assistant_repo.count_plans_by_status(db)
    return [PlanStatusCount(**row) for row in rows]


async def list_patients_by_plan_status_tool(db, status: str) -> list[PatientPlanStatusRef]:
    status = _require(status, "status").upper()
    rows = await assistant_repo.list_patients_by_plan_status(db, status)
    return [PatientPlanStatusRef(**row) for row in rows]
