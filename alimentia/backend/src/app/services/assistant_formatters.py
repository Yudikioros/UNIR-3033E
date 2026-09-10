"""
Builders de texto determinísticos para respuestas frecuentes (sección 12 de
la corrección). Ninguna función de este módulo llama al LLM: reciben los DTOs
ya devueltos por las herramientas (`assistant_tools.py`) y arman texto plano
directamente. Esto es lo que permite que la mayoría de las preguntas
respondan en milisegundos en vez de ~180s.
"""
from app.schemas.assistant import (
    AssistantCalculationDetail, AssistantConsultationSummary, AssistantPatientRef, AssistantPatientSummary,
    AssistantPlanDetail, AssistantPlanSummary, PatientPlanStatusRef, PlanStatusCount, PlanVersionComparison,
)

_STATUS_LABELS = {"DRAFT": "borrador", "UNDER_REVIEW": "en revisión", "MODIFIED": "modificado",
    "REGENERATED": "regenerado", "APPROVED": "aprobado", "REJECTED": "rechazado"}


def _status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status)


def format_patient_not_found(name: str) -> str:
    return f'No encontré ningún paciente llamado "{name}" en AlimentIA.'


def format_multiple_patients(name: str, matches: list[AssistantPatientRef]) -> str:
    names = "; ".join(match.name for match in matches)
    return f'Encontré más de un paciente que coincide con "{name}": {names}. ¿A cuál de ellos te refieres?'


def format_patient_summary(patient: AssistantPatientSummary) -> str:
    parts = [f"{patient.name}."]
    if patient.currentAge is not None:
        parts.append(f"Edad: {patient.currentAge} años.")
    if patient.defaultGoal:
        parts.append(f"Objetivo habitual: {patient.defaultGoal}.")
    if patient.conditions:
        parts.append(f"Condiciones registradas: {', '.join(patient.conditions)}.")
    return " ".join(parts)


def format_patient_plans(patient_name: str, plans: list[AssistantPlanSummary]) -> str:
    if not plans:
        return f"{patient_name} todavía no tiene ningún plan generado en AlimentIA."
    lines = [f"{patient_name} tiene {len(plans)} plan(es):"]
    for plan in sorted(plans, key=lambda p: (p.consultationId, p.version)):
        energy = f"{plan.totalCalories:.0f} kcal" if plan.totalCalories is not None else "sin energía calculada"
        lines.append(f"- Versión {plan.version} ({_status_label(plan.status)}): {energy}.")
    return "\n".join(lines)


def format_patient_consultations(patient_name: str, consultations: list[AssistantConsultationSummary]) -> str:
    if not consultations:
        return f"{patient_name} todavía no tiene ninguna consulta registrada en AlimentIA."
    lines = [f"{patient_name} tiene {len(consultations)} consulta(s):"]
    for consultation in sorted(consultations, key=lambda c: c.consultationDate, reverse=True):
        date = consultation.consultationDate.strftime("%d/%m/%Y")
        target = f"{consultation.targetCalories:.0f} kcal" if consultation.targetCalories is not None else "sin cálculo registrado"
        lines.append(f"- {date}: objetivo {target}.")
    return "\n".join(lines)


def format_calculation_summary(patient_name: str | None, calculation: AssistantCalculationDetail) -> str:
    who = f"de {patient_name} " if patient_name else ""
    lines = [f"Cálculo nutricional {who}(método {calculation.calculationMethod}, ruleset {calculation.calculationRuleVersion}):"]
    if calculation.basalMetabolicRate is not None:
        lines.append(f"- Tasa metabólica basal (BMR): {calculation.basalMetabolicRate:.0f} kcal.")
    if calculation.activityFactor is not None:
        lines.append(f"- Factor de actividad: {calculation.activityFactor}.")
    if calculation.totalEnergyExpenditure is not None:
        lines.append(f"- Gasto energético total (TDEE): {calculation.totalEnergyExpenditure:.0f} kcal.")
    if calculation.goalAdjustmentKcal is not None:
        lines.append(f"- Ajuste por objetivo: {calculation.goalAdjustmentKcal:+.0f} kcal.")
    if calculation.targetCalories is not None:
        lines.append(f"- Energía objetivo final: {calculation.targetCalories:.0f} kcal.")
    if calculation.proteinGrams is not None:
        lines.append(f"- Macronutrientes objetivo: {calculation.proteinGrams:.0f} g proteína, "
                      f"{calculation.carbohydrateGrams:.0f} g carbohidratos, {calculation.fatGrams:.0f} g grasa.")
    return "\n".join(lines)


def format_plan_detail(plan: AssistantPlanDetail) -> str:
    lines = [f"Plan versión {plan.version} — estado: {_status_label(plan.status)}."]
    if plan.totalCalories is not None:
        target = f" (objetivo: {plan.targetCalories:.0f} kcal)." if plan.targetCalories is not None else "."
        lines.append(f"Energía del plan: {plan.totalCalories:.0f} kcal{target}")
    elif plan.targetCalories is not None:
        lines.append(f"Energía del plan: no calculada todavía (objetivo: {plan.targetCalories:.0f} kcal).")
    lines.append(f"Comidas: {len(plan.meals)}.")
    for meal in plan.meals:
        food_names = ", ".join(food.foodName for food in meal.foods) or "sin alimentos"
        lines.append(f"- {meal.mealType} ({meal.name}): {food_names}.")
    if plan.blockingValidationCount:
        lines.append(f"Tiene {plan.blockingValidationCount} validación(es) bloqueante(s) pendiente(s).")
    return "\n".join(lines)


def format_plan_validations(plan: AssistantPlanDetail) -> str:
    if not plan.validations:
        return f"El plan versión {plan.version} no tiene validaciones registradas."
    blocking = [v for v in plan.validations if v.isBlocking]
    warnings = [v for v in plan.validations if not v.isBlocking and v.severity == "WARNING"]
    info = [v for v in plan.validations if not v.isBlocking and v.severity != "WARNING"]
    lines = [f"El plan versión {plan.version} tiene {len(plan.validations)} validación(es):"]
    if blocking:
        lines.append("Bloqueantes:")
        lines.extend(f"{i + 1}. {v.message}" for i, v in enumerate(blocking))
    if warnings:
        lines.append("Advertencias:")
        lines.extend(f"- {v.message}" for v in warnings)
    if info:
        lines.append("Informativas:")
        lines.extend(f"- {v.message}" for v in info)
    return "\n".join(lines)


def format_plan_approval_status(plan: AssistantPlanDetail) -> str:
    if plan.status == "APPROVED":
        return f"El plan versión {plan.version} ya está aprobado."
    if plan.status == "REJECTED":
        reason = f": {plan.rejectionReason}." if plan.rejectionReason else "."
        return f"El plan versión {plan.version} fue rechazado{reason}"
    if plan.blockingValidationCount == 0:
        return f"El plan versión {plan.version} no tiene validaciones bloqueantes y puede aprobarse."
    blocking = [v for v in plan.validations if v.isBlocking]
    lines = [f"El plan versión {plan.version} tiene {plan.blockingValidationCount} validación(es) "
             "bloqueante(s) y no puede aprobarse todavía:"]
    lines.extend(f"{i + 1}. {v.message}" for i, v in enumerate(blocking))
    return "\n".join(lines)


def format_plan_counts(counts: list[PlanStatusCount]) -> str:
    if not counts:
        return "Todavía no hay ningún plan generado en AlimentIA."
    lines = ["Planes por estado:"]
    lines.extend(f"- {_status_label(count.status)}: {count.count}." for count in counts)
    return "\n".join(lines)


def format_patients_by_status(status: str, rows: list[PatientPlanStatusRef]) -> str:
    if not rows:
        return f'No hay ningún paciente con planes en estado "{_status_label(status)}" actualmente.'
    lines = [f'Pacientes con planes en estado "{_status_label(status)}":']
    seen: set[str] = set()
    for row in rows:
        if row.patientId in seen:
            continue
        seen.add(row.patientId)
        lines.append(f"- {row.patientName} (versión {row.version}).")
    return "\n".join(lines)


def format_knowledge_sources(sources) -> str:
    if not sources:
        return "No hay fuentes documentales configuradas actualmente en AlimentIA."
    lines = ["Fuentes documentales autorizadas:"]
    for source in sources:
        state = "activa" if source.isActive else "histórica/inactiva"
        institution = f" — {source.institution}" if source.institution else ""
        lines.append(f"- {source.documentName}{institution} ({state}).")
    return "\n".join(lines)


def format_plan_comparison(comparison: PlanVersionComparison) -> str:
    lines = [f"Comparación: versión {comparison.planA.version} ({_status_label(comparison.planA.status)}) "
             f"vs. versión {comparison.planB.version} ({_status_label(comparison.planB.status)})."]
    if comparison.totalCaloriesDelta is not None:
        lines.append(f"Diferencia de energía: {comparison.totalCaloriesDelta:+.0f} kcal.")
    lines.append(f"Comidas: {comparison.mealCountA} → {comparison.mealCountB}.")
    if comparison.foodsAdded:
        lines.append(f"Alimentos agregados: {', '.join(comparison.foodsAdded)}.")
    if comparison.foodsRemoved:
        lines.append(f"Alimentos quitados: {', '.join(comparison.foodsRemoved)}.")
    if comparison.quantityChanges:
        changes = "; ".join(f"{change['foodName']}: {change['before']}→{change['after']}"
                             for change in comparison.quantityChanges)
        lines.append(f"Cambios de cantidad: {changes}.")
    return "\n".join(lines)
