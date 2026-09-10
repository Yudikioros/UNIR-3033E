"""Compatibility adapter for existing routes; no new LLM or workflow behavior."""
from dataclasses import dataclass
from datetime import datetime, timezone
from app.repositories.normalized import dietary_create, dietary_projection

LEGACY_STATUS = {
    'DRAFT': 'BORRADOR', 'UNDER_REVIEW': 'EN REVISIÓN', 'MODIFIED': 'MODIFICADO',
    'REGENERATED': 'REGENERADO', 'REJECTED': 'RECHAZADO', 'APPROVED': 'PLAN APROBADO',
}
GOALS = {'WEIGHT_LOSS': 'Pérdida de peso', 'MAINTENANCE': 'Mantenimiento', 'WEIGHT_GAIN': 'Ganancia muscular'}
PATIENT_INCLUDE = {'conditions': True, 'dietaryItems': True, 'legacySnapshot': True}
PLAN_INCLUDE = {'legacySnapshot': True, 'nutrientObservations': True}


def legacy_patient(patient):
    value = patient.model_dump(exclude={'consultations', 'conditions', 'dietaryItems', 'legacySnapshot'})
    value['gender'] = value.pop('sex')
    value['goal'] = GOALS.get(patient.defaultGoal, patient.defaultGoal or '')
    value['pathologies'] = ', '.join(c.description for c in patient.conditions or [])
    value.update(dietary_projection(patient.dietaryItems))
    return value


def legacy_plan(plan, patient_id, patient=None):
    value = plan.model_dump(exclude={'consultation', 'legacySnapshot', 'nutrientObservations'})
    value['status'] = LEGACY_STATUS.get(value['status'], value['status'])
    value['patientId'] = patient_id
    # These are original document attributes, not current calculated totals.
    source = plan.legacySnapshot
    value['plan_json'] = source.originalPlanJson if source else None
    value['tdee_calculated'] = source.originalTdee if source else None
    value.update({m.metricCode: m.value for m in plan.nutrientObservations or []})
    if patient:
        value['patient'] = legacy_patient(patient)
    return value


async def list_patients(db):
    patients = await db.patient.find_many(include={**PATIENT_INCLUDE,
        'consultations': {'include': {'plans': {'include': PLAN_INCLUDE}}}}, order={'createdAt': 'desc'})
    result = []
    for patient in patients:
        value = legacy_patient(patient)
        plans = [p for c in patient.consultations or [] for p in c.plans or []]
        value['plans'] = [legacy_plan(p, patient.id) for p in sorted(plans, key=lambda p: p.createdAt, reverse=True)]
        result.append(value)
    return result


async def list_plans(db):
    plans = await db.dietplan.find_many(include={**PLAN_INCLUDE,
        'consultation': {'include': {'patient': {'include': PATIENT_INCLUDE}}}}, order={'createdAt': 'desc'})
    return [legacy_plan(plan, plan.consultation.patientId, plan.consultation.patient) for plan in plans]


@dataclass
class SavedLegacyDraft:
    id: str
    plans: list


async def save_legacy_draft(db, patient, requirements, plan):
    """Persist existing generation output atomically into the normalized relations."""
    async with db.tx() as tx:
        created = await tx.patient.create(data={
            'age': patient.age, 'ageRecordedAt': datetime.now(timezone.utc), 'sex': patient.gender,
            'defaultGoal': next((k for k, v in GOALS.items() if v == patient.goal), patient.goal),
            'conditions': {'create': [{'description': p} for p in dict.fromkeys(patient.pathologies or []) if p.strip()]},
        })
        consultation = await tx.nutritionconsultation.create(data=dietary_create({
            'patientId': created.id, 'ageAtConsultation': patient.age, 'sex': patient.gender,
            'weightKg': patient.weight, 'heightM': patient.height,
            'activityLevel': patient.activity_level, 'goal': patient.goal,
            'foodPreferences': patient.food_preferences,
            'allergiesOrIntolerances': patient.allergies_intolerances,
            'calculations': {'create': [{'calculationMethod': 'MIFFLIN_ST_JEOR',
                'metrics': {'create': [
                    {'metricCode': 'basalMetabolicRate', 'value': requirements['bmr_kcal']},
                    {'metricCode': 'totalEnergyExpenditure', 'value': requirements['tdee_kcal']},
                ]}}]},
            'notes': 'Created by legacy generation endpoint; budget: ' + (patient.budget or ''),
        }))
        saved = await tx.dietplan.create(data={
            'consultationId': consultation.id, 'status': 'DRAFT',
            'legacySnapshot': {'create': {'originalPatientId': created.id,
                'originalTdee': requirements['tdee_kcal'], 'originalPlanJson': plan.model_dump_json(),
                'originalStatus': 'BORRADOR'}},
        }, include={'legacySnapshot': True})
        return SavedLegacyDraft(id=created.id, plans=[saved])
