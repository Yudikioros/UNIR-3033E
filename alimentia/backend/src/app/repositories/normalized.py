"""Persistence projections: API convenience fields are assembled, never duplicated in tables."""
import json
from datetime import datetime, timezone

DIETARY_FIELDS = {
    'foodPreferences': 'PREFERENCE', 'foodsToAvoid': 'AVOID',
    'allergiesOrIntolerances': 'ALLERGY_OR_INTOLERANCE',
}
CALCULATION_FIELDS = ('bmi', 'basalMetabolicRate', 'totalEnergyExpenditure',
    'targetCalories', 'proteinGrams', 'carbohydrateGrams', 'fatGrams', 'fiberGrams', 'waterLiters')


def dietary_values(raw):
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except (ValueError, TypeError):
            decoded = raw
        raw = decoded if isinstance(decoded, list) else [raw]
    if not isinstance(raw, list) or any(not isinstance(v, str) for v in raw):
        raise ValueError('Dietary items must be strings')
    return list(dict.fromkeys(v for v in raw if v.strip()))


def dietary_create(data):
    items = []
    for field, kind in DIETARY_FIELDS.items():
        items.extend({'kind': kind, 'content': value} for value in dietary_values(data.pop(field, None)))
    if items:
        data['dietaryItems'] = {'create': items}
    return data


async def create_patient(db, dto):
    data = dietary_create(dto.model_dump(exclude_none=True))
    if data.get('age') is not None:
        data['ageRecordedAt'] = datetime.now(timezone.utc)
    return await db.patient.create(data=data)


async def create_consultation(db, dto):
    data = dietary_create(dto.model_dump(exclude_none=True))
    method = data.pop('calculationMethod', None)
    if method:
        data['calculations'] = {'create': [{'calculationMethod': method}]}
    return await db.nutritionconsultation.create(data=data)


def dietary_projection(items):
    return {field: json.dumps([item.content for item in items or [] if item.kind == kind], ensure_ascii=False)
            for field, kind in DIETARY_FIELDS.items()}


def patient_read(patient):
    """Call with dietaryItems included; birthDate and age are mutually exclusive."""
    from app.schemas.persistence import PatientRead
    data = {k: v for k, v in patient.model_dump().items() if k in PatientRead.model_fields}
    data.update(dietary_projection(patient.dietaryItems))
    return PatientRead.model_validate(data)


def consultation_read(consultation):
    """Call with dietaryItems and calculations.metrics included."""
    from app.schemas.persistence import NutritionConsultationRead
    fields = NutritionConsultationRead.model_fields
    data = {k: v for k, v in consultation.model_dump().items() if k in fields}
    data.update(dietary_projection(consultation.dietaryItems))
    runs = sorted(consultation.calculations or [], key=lambda r: (r.recordedAt, r.id), reverse=True)
    if runs:
        latest = runs[0]
        data.update({k: getattr(latest, k) for k in ('calculationMethod','calculationRuleVersion','calculationDetails')})
        data.update({m.metricCode: m.value for m in latest.metrics or [] if m.metricCode in CALCULATION_FIELDS})
    return NutritionConsultationRead.model_validate(data)


def plan_read(plan):
    """Call with meals.foods, nutrientObservations and generationLinks included."""
    from app.schemas.persistence import DietPlanRead
    data = {k: v for k, v in plan.model_dump().items() if k in DietPlanRead.model_fields}
    data['meals'] = plan.meals or []
    data.update({m.metricCode: m.value for m in plan.nutrientObservations or [] if m.metricCode in DietPlanRead.model_fields})
    data['generationId'] = next((l.generationId for l in plan.generationLinks or [] if l.isOrigin), None)
    try:
        data['recommendations'] = json.loads(plan.recommendations) if plan.recommendations else []
    except (ValueError, TypeError):
        data['recommendations'] = []
    return DietPlanRead.model_validate(data)
