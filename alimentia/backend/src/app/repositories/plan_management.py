"""
Ciclo de vida human-in-the-loop del plan (Fase 5): consulta, edición manual,
aprobación, rechazo y regeneración.

Principio: EL PLAN NUNCA SE CONSIDERA FINAL HASTA QUE UN PROFESIONAL LO
APRUEBA EXPLÍCITAMENTE. Reutiliza `DietPlanChangeLog` (Fase 1) como única
auditoría — no crea un sistema paralelo. Reutiliza `PlanStatus` (DRAFT,
UNDER_REVIEW, MODIFIED, REGENERATED, REJECTED, APPROVED) ya definido y con
CHECK en la base de datos — no duplica el enum.

Transiciones permitidas:

    DRAFT | UNDER_REVIEW  --edit-->        UNDER_REVIEW (mismo DietPlan)
    DRAFT | UNDER_REVIEW  --approve-->     APPROVED (si no hay validaciones bloqueantes)
    DRAFT | UNDER_REVIEW  --reject-->      REJECTED
    DRAFT | UNDER_REVIEW | REJECTED --regenerate--> nueva versión DRAFT (plan actual intacto)
    APPROVED                               inmutable: edit/approve/reject/regenerate -> 409
    REJECTED                               no editable directamente (no vuelve a DRAFT solo); sí regenerable

`parentPlanId` no existe en el schema y no se agrega por comodidad (sección
20 de Fase 5): la relación entre versiones se infiere por
`consultationId` + `version` (siempre consecutivo, nunca reutilizado).
"""
import os
from datetime import datetime, timezone

from app.repositories.capture import CaptureError, get_consultation
from app.repositories.normalized import consultation_read, dietary_values, plan_read
from app.schemas.generation import PlanValidationRead, RetrievedSourceRead
from app.schemas.plan_management import DietPlanDetail
from app.services import diet_plan_generation, plan_validation

EDITABLE_STATUSES = {"DRAFT", "UNDER_REVIEW"}
APPROVABLE_STATUSES = {"DRAFT", "UNDER_REVIEW"}
REJECTABLE_STATUSES = {"DRAFT", "UNDER_REVIEW"}
REGENERATABLE_STATUSES = {"DRAFT", "UNDER_REVIEW", "REJECTED"}

# Identidad profesional mínima (sección 7): nunca "Nutriólogo" genérico a secas;
# un identificador explícito de actor de sistema para este despliegue de demo/dev,
# hasta que exista autenticación real.
DEFAULT_ACTOR = os.getenv("ALIMENTIA_DEFAULT_ACTOR", "profesional-demo")

PLAN_INCLUDE = {
    "meals": {"include": {"foods": True}},
    "nutrientObservations": True,
    "generationLinks": {"include": {"generation": True}},
    "validations": True,
}


def now():
    return datetime.now(timezone.utc)


def _actor(value) -> str:
    value = (value or "").strip()
    return value or DEFAULT_ACTOR


def _validation_read(row) -> PlanValidationRead:
    data = {k: v for k, v in row.model_dump().items() if k in PlanValidationRead.model_fields}
    return PlanValidationRead.model_validate(data)


async def _sources_for_plan(db, plan) -> list:
    origin_link = next((link for link in plan.generationLinks or [] if link.isOrigin), None)
    if origin_link is None:
        return []
    rows = await db.retrievedsource.find_many(where={"generationId": origin_link.generationId}, include={"knowledgeSource": True})
    return [RetrievedSourceRead(id=row.id, knowledgeSourceId=row.knowledgeSourceId,
        documentName=row.knowledgeSource.documentName, institution=row.knowledgeSource.institution,
        section=row.section, retrievalScore=row.retrievalScore) for row in rows]


async def _plan_detail(db, plan, consultation_targets=None) -> DietPlanDetail:
    if consultation_targets is None:
        consultation = await get_consultation(db, plan.consultationId)
        consultation_targets = consultation_read(consultation)

    origin_link = next((link for link in plan.generationLinks or [] if link.isOrigin), None)
    generation = origin_link.generation if origin_link else None

    base = plan_read(plan)
    validations = [_validation_read(v) for v in plan.validations or []]
    sources = await _sources_for_plan(db, plan)

    return DietPlanDetail(
        **base.model_dump(),
        targetCalories=consultation_targets.targetCalories, targetProteinGrams=consultation_targets.proteinGrams,
        targetCarbohydrateGrams=consultation_targets.carbohydrateGrams, targetFatGrams=consultation_targets.fatGrams,
        targetFiberGrams=consultation_targets.fiberGrams, targetWaterLiters=consultation_targets.waterLiters,
        validations=validations, sources=sources,
        blockingValidationCount=sum(1 for v in validations if v.isBlocking),
        isEditable=plan.status in EDITABLE_STATUSES,
        generatedAt=generation.createdAt if generation else None,
        modelProvider=generation.modelProvider if generation else None,
        modelName=generation.modelName if generation else None,
        promptVersion=generation.promptVersion if generation else None,
        knowledgeBaseVersion=generation.knowledgeBaseVersion if generation else None,
    )


async def get_plan(db, plan_id: str):
    plan = await db.dietplan.find_unique(where={"id": plan_id}, include=PLAN_INCLUDE)
    if plan is None:
        raise CaptureError(404, "No se encontró el plan.")
    return plan


async def get_plan_detail(db, plan_id: str) -> DietPlanDetail:
    plan = await get_plan(db, plan_id)
    return await _plan_detail(db, plan)


async def list_consultation_plans(db, consultation_id: str) -> list:
    consultation = await get_consultation(db, consultation_id)  # 404 si la consulta no existe
    targets = consultation_read(consultation)
    rows = await db.dietplan.find_many(where={"consultationId": consultation_id},
        include=PLAN_INCLUDE, order={"version": "asc"})
    return [await _plan_detail(db, row, consultation_targets=targets) for row in rows]


def _meal_snapshot(meal) -> dict:
    # Sin columna de orden propia en DietPlanFood: se conserva el orden de
    # inserción tal como lo devuelve Prisma/SQLite (nunca se ordena por id,
    # que es un UUID sin relación con el orden real).
    return {
        "mealType": meal.mealType, "name": meal.name, "sortOrder": meal.sortOrder,
        "foods": [{"foodName": f.foodName, "quantity": f.quantity, "unit": f.unit,
                   "calories": f.calories, "protein": f.protein, "carbohydrates": f.carbohydrates,
                   "fat": f.fat, "smaeEquivalent": f.smaeEquivalent, "notes": f.notes}
                  for f in (meal.foods or [])],
    }


def _stringify(value):
    return None if value is None else str(value)


def _diff_foods(meal_index: int, previous: list, new: list) -> list:
    entries = []
    fields = ("foodName", "quantity", "unit", "calories", "protein", "carbohydrates", "fat", "smaeEquivalent", "notes")
    for i in range(max(len(previous), len(new))):
        old_food = previous[i] if i < len(previous) else None
        new_food = new[i] if i < len(new) else None
        if old_food is None:
            entries.append({"field": f"meals[{meal_index}].foods[{i}]", "previousValue": None,
                             "newValue": new_food["foodName"]})
            continue
        if new_food is None:
            entries.append({"field": f"meals[{meal_index}].foods[{i}]", "previousValue": old_food["foodName"],
                             "newValue": None})
            continue
        for field in fields:
            if old_food.get(field) != new_food.get(field):
                entries.append({"field": f"meals[{meal_index}].foods[{i}].{field}",
                    "previousValue": _stringify(old_food.get(field)), "newValue": _stringify(new_food.get(field))})
    return entries


def _diff_meals(previous: list, new: list) -> list:
    """Diferencia posicional simple: suficiente para registrar qué cambió (sección 6),
    no pretende detectar reordenamientos semánticos como "el mismo platillo se movió"."""
    entries = []
    for i in range(max(len(previous), len(new))):
        old_meal = previous[i] if i < len(previous) else None
        new_meal = new[i] if i < len(new) else None
        if old_meal is None:
            entries.append({"field": f"meals[{i}]", "previousValue": None, "newValue": new_meal["name"]})
            continue
        if new_meal is None:
            entries.append({"field": f"meals[{i}]", "previousValue": old_meal["name"], "newValue": None})
            continue
        if old_meal["name"] != new_meal["name"]:
            entries.append({"field": f"meals[{i}].name", "previousValue": old_meal["name"], "newValue": new_meal["name"]})
        if old_meal["mealType"] != new_meal["mealType"]:
            entries.append({"field": f"meals[{i}].mealType", "previousValue": old_meal["mealType"], "newValue": new_meal["mealType"]})
        entries.extend(_diff_foods(i, old_meal["foods"], new_meal["foods"]))
    return entries


async def _revalidate(tx, plan_id: str, meals: list, *, meals_per_day, target_calories, restricted_terms) -> list:
    """PlanValidationService (sección 9): recalcula totales y validaciones desde
    los alimentos persistidos, siempre en base al objetivo real de la consulta."""
    await tx.planvalidation.delete_many(where={"dietPlanId": plan_id})
    validations = plan_validation.validate_meals(meals, meals_per_day=meals_per_day,
        target_calories=target_calories, restricted_terms=restricted_terms)
    for validation in validations:
        await tx.planvalidation.create(data={"dietPlanId": plan_id, **validation})

    await tx.plannutrientobservation.delete_many(where={"dietPlanId": plan_id})
    for code, value in plan_validation.plan_totals(meals).items():
        await tx.plannutrientobservation.create(data={"dietPlanId": plan_id, "metricCode": code, "value": value})
    return validations


async def edit_plan(db, plan_id: str, dto) -> DietPlanDetail:
    async with db.tx() as tx:
        plan = await tx.dietplan.find_unique(where={"id": plan_id},
            include={"meals": {"include": {"foods": True}}})
        if plan is None:
            raise CaptureError(404, "No se encontró el plan.")
        if plan.status not in EDITABLE_STATUSES:
            raise CaptureError(409, "Este plan ya no admite edición directa en su estado actual.")
        if dto.expectedUpdatedAt is not None and plan.updatedAt != dto.expectedUpdatedAt:
            raise CaptureError(409, "El plan cambió en otra sesión. Recarga antes de guardar.")

        consultation = await get_consultation(tx, plan.consultationId)
        targets = consultation_read(consultation)
        restricted_terms = dietary_values(targets.foodsToAvoid) + dietary_values(targets.allergiesOrIntolerances)

        actor = _actor(dto.actor)
        previous_meals = [_meal_snapshot(m) for m in sorted(plan.meals or [], key=lambda m: m.sortOrder)]
        new_meals = [{"mealType": meal.mealType, "name": meal.name, "sortOrder": index,
            "foods": [food.model_dump() for food in meal.foods]}
            for index, meal in enumerate(dto.meals)]

        # Un mismo guardado puede generar varias entradas de auditoría (una por campo
        # cambiado, para el detalle del historial); todas comparten `changedAt` para que
        # la trazabilidad y las métricas de Fase 6 puedan contar "ediciones" (guardados)
        # en vez de "campos cambiados", agrupando por este timestamp compartido.
        edited_at = now()
        for entry in _diff_meals(previous_meals, new_meals):
            await tx.dietplanchangelog.create(data={"dietPlanId": plan_id, "changedBy": actor,
                "changeType": "MANUAL_EDIT", "changedAt": edited_at, **entry})

        meal_ids = [m.id for m in plan.meals or []]
        if meal_ids:
            await tx.dietplanfood.delete_many(where={"dietPlanMealId": {"in": meal_ids}})
            await tx.dietplanmeal.delete_many(where={"id": {"in": meal_ids}})
        for meal in new_meals:
            await tx.dietplanmeal.create(data={"dietPlanId": plan_id, "mealType": meal["mealType"],
                "name": meal["name"], "sortOrder": meal["sortOrder"], "foods": {"create": meal["foods"]}})

        next_status = "UNDER_REVIEW" if plan.status == "DRAFT" else plan.status
        await tx.dietplan.update(where={"id": plan_id}, data={"status": next_status, "updatedAt": now()})
        await _revalidate(tx, plan_id, new_meals, meals_per_day=consultation.mealsPerDay,
            target_calories=targets.targetCalories, restricted_terms=restricted_terms)

        full_plan = await tx.dietplan.find_unique(where={"id": plan_id}, include=PLAN_INCLUDE)
        return await _plan_detail(tx, full_plan, consultation_targets=targets)


async def approve_plan(db, plan_id: str, dto) -> DietPlanDetail:
    plan = await db.dietplan.find_unique(where={"id": plan_id}, include={"meals": {"include": {"foods": True}}})
    if plan is None:
        raise CaptureError(404, "No se encontró el plan.")
    if plan.status == "APPROVED":
        raise CaptureError(409, "Este plan ya fue aprobado.")
    if plan.status not in APPROVABLE_STATUSES:
        raise CaptureError(409, "Este plan no admite aprobación en su estado actual.")
    if not plan.meals:
        raise CaptureError(409, "El plan no contiene comidas; no puede aprobarse.")

    consultation = await get_consultation(db, plan.consultationId)
    targets = consultation_read(consultation)
    restricted_terms = dietary_values(targets.foodsToAvoid) + dietary_values(targets.allergiesOrIntolerances)
    meals = [_meal_snapshot(m) for m in sorted(plan.meals or [], key=lambda m: m.sortOrder)]

    # Sección 12: "el plan fue validado después de la última modificación" se garantiza
    # revalidando siempre, en su propia transacción, que SIEMPRE se confirma — a diferencia
    # de la aprobación en sí, que puede rechazarse después. Si ambos pasos compartieran una
    # sola transacción, un 409 más abajo revertiría también esta revalidación recién hecha.
    async with db.tx() as tx:
        validations = await _revalidate(tx, plan_id, meals, meals_per_day=consultation.mealsPerDay,
            target_calories=targets.targetCalories, restricted_terms=restricted_terms)

    blocking = [v for v in validations if v["isBlocking"]]
    if blocking:
        raise CaptureError(409, "El plan contiene validaciones que deben resolverse antes de aprobarlo.",
            extra={"blockingValidations": blocking})

    actor = _actor(dto.actor)
    async with db.tx() as tx:
        await tx.dietplan.update(where={"id": plan_id}, data={
            "status": "APPROVED", "approvedAt": now(), "approvedBy": actor,
            "rejectedAt": None, "rejectedBy": None, "rejectionReason": None, "updatedAt": now(),
        })
        await tx.dietplanchangelog.create(data={"dietPlanId": plan_id, "changedBy": actor,
            "changeType": "APPROVAL", "field": "status", "previousValue": plan.status, "newValue": "APPROVED"})

        full_plan = await tx.dietplan.find_unique(where={"id": plan_id}, include=PLAN_INCLUDE)
        return await _plan_detail(tx, full_plan, consultation_targets=targets)


async def reject_plan(db, plan_id: str, dto) -> DietPlanDetail:
    async with db.tx() as tx:
        plan = await tx.dietplan.find_unique(where={"id": plan_id})
        if plan is None:
            raise CaptureError(404, "No se encontró el plan.")
        if plan.status == "APPROVED":
            raise CaptureError(409, "Un plan aprobado no puede rechazarse.")
        if plan.status not in REJECTABLE_STATUSES:
            raise CaptureError(409, "Este plan no admite rechazo en su estado actual.")

        actor = _actor(dto.actor)
        await tx.dietplan.update(where={"id": plan_id}, data={
            "status": "REJECTED", "rejectedAt": now(), "rejectedBy": actor,
            "rejectionReason": dto.reason, "updatedAt": now(),
        })
        await tx.dietplanchangelog.create(data={"dietPlanId": plan_id, "changedBy": actor,
            "changeType": "REJECTION", "field": "status", "previousValue": plan.status,
            "newValue": "REJECTED", "notes": dto.reason})

        full_plan = await tx.dietplan.find_unique(where={"id": plan_id}, include=PLAN_INCLUDE)
        return await _plan_detail(tx, full_plan)


async def _check_regeneratable(db, plan_id: str):
    plan = await db.dietplan.find_unique(where={"id": plan_id})
    if plan is None:
        raise CaptureError(404, "No se encontró el plan.")
    if plan.status not in REGENERATABLE_STATUSES:
        raise CaptureError(409, "No es posible regenerar a partir de un plan aprobado.")
    return plan


async def regenerate_plan(db, plan_id: str, dto, *, llm_client=None):
    """Crea una nueva versión (DRAFT) para la misma consulta. El plan de origen
    permanece intacto: nunca se sobrescribe ni se borra historial. Variante
    síncrona (se mantiene por compatibilidad): espera bloqueada a que termine."""
    plan = await _check_regeneratable(db, plan_id)
    actor = _actor(dto.actor)
    result = await diet_plan_generation.regenerate_draft(db, plan.consultationId,
        instructions=dto.instructions, llm_client=llm_client)

    await db.dietplanchangelog.create(data={"dietPlanId": plan_id, "changedBy": actor,
        "changeType": "REGENERATION_REQUESTED", "field": "version",
        "previousValue": str(plan.version), "newValue": str(result.version),
        "notes": (dto.instructions or None)})
    return result


async def start_regeneration_job(db, plan_id: str, dto, *, llm_client=None) -> str:
    """Corrección de UX: misma validación y mismo resultado final que
    `regenerate_plan`, pero responde de inmediato con el id de la generación
    en curso -el frontend hace polling de /generations/{id}/status- y solo
    escribe el registro de auditoría (DietPlanChangeLog) una vez que la
    generación en segundo plano termina con éxito, igual que hoy."""
    plan = await _check_regeneratable(db, plan_id)
    actor = _actor(dto.actor)
    generation_id, consultation, client = await diet_plan_generation.prepare_generation_job(
        db, plan.consultationId, llm_client=llm_client)

    async def _background():
        try:
            result = await diet_plan_generation.run_generation_job(db, plan.consultationId,
                instructions=dto.instructions, llm_client=client, generation_id=generation_id,
                consultation=consultation)
        except Exception:
            return  # ya quedó registrado como FAILED por run_generation_job
        await db.dietplanchangelog.create(data={"dietPlanId": plan_id, "changedBy": actor,
            "changeType": "REGENERATION_REQUESTED", "field": "version",
            "previousValue": str(plan.version), "newValue": str(result.version),
            "notes": (dto.instructions or None)})

    diet_plan_generation.spawn_background(_background())
    return generation_id
