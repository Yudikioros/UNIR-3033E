"""Replace the evaluation demo cases without touching unrelated clinical records."""
import asyncio
from datetime import datetime, timezone
from prisma import Prisma

CASES = [
    {
        'id': 'CASE-01', 'name': 'María González', 'age': 28, 'sex': 'female',
        'weight': 68.0, 'height': 1.60, 'activity': 'moderate',
        'goal': 'WEIGHT_LOSS', 'goalCode': 'perdida_grasa',
        'restrictions': ['intolerancia_lactosa', 'no_mariscos'],
        'groundTruth': {'tmb': 1379, 'calorias_meta': 1850, 'proteinas_g': 120,
                        'lipidos_g': 60, 'carbohidratos_g': 210, 'fibra_g': 28, 'agua_l': 2.1},
    },
    {
        'id': 'CASE-02', 'name': 'Estefanía Gómez Casillas', 'age': 25, 'sex': 'female',
        'weight': 75.0, 'height': 1.62, 'activity': 'moderate',
        'goal': 'WEIGHT_LOSS', 'goalCode': 'control_glucemico_deficit',
        'restrictions': ['sin_azucares_refinados'],
        'groundTruth': {'tmb': 1476, 'calorias_meta': 1800, 'proteinas_g': 110,
                        'lipidos_g': 65, 'carbohidratos_g': 195, 'fibra_g': 32, 'agua_l': 2.3},
    },
    {
        'id': 'CASE-03', 'name': 'Jorge Alcántara', 'age': 41, 'sex': 'male',
        'weight': 78.0, 'height': 1.75, 'activity': 'light',
        'goal': 'MAINTENANCE', 'goalCode': 'mantenimiento_cardiovascular',
        'restrictions': ['sin_carnes_rojas_grasas', 'bajo_sodio'],
        'groundTruth': {'tmb': 1674, 'calorias_meta': 2300, 'proteinas_g': 125,
                        'lipidos_g': 70, 'carbohidratos_g': 290, 'fibra_g': 30, 'agua_l': 2.5},
    },
    {
        'id': 'CASE-04', 'name': 'Lucía Ramírez', 'age': 34, 'sex': 'female',
        'weight': 58.0, 'height': 1.65, 'activity': 'active',
        'goal': 'WEIGHT_GAIN', 'goalCode': 'hipertrofia_superavit', 'restrictions': [],
        'groundTruth': {'tmb': 1280, 'calorias_meta': 2400, 'proteinas_g': 116,
                        'lipidos_g': 65, 'carbohidratos_g': 338, 'fibra_g': 26, 'agua_l': 2.6},
    },
    {
        'id': 'CASE-05', 'name': 'Roberto Domínguez', 'age': 58, 'sex': 'male',
        'weight': 72.0, 'height': 1.68, 'activity': 'sedentary',
        'goal': 'MAINTENANCE', 'goalCode': 'mantenimiento_economico',
        'restrictions': ['texturas_suaves', 'bajo_costo'],
        'groundTruth': {'tmb': 1485, 'calorias_meta': 1750, 'proteinas_g': 88,
                        'lipidos_g': 50, 'carbohidratos_g': 237, 'fibra_g': 25, 'agua_l': 2.0},
    },
]
METRIC_CODES = {
    'tmb': 'BASAL_METABOLIC_RATE', 'calorias_meta': 'TARGET_CALORIES',
    'proteinas_g': 'PROTEIN_GRAMS', 'lipidos_g': 'FAT_GRAMS',
    'carbohidratos_g': 'CARBOHYDRATE_GRAMS', 'fibra_g': 'FIBER_GRAMS',
    'agua_l': 'WATER_LITERS',
}
LEGACY_DEMO_KEYS = ['phase1-maria-mvp', 'phase1-maria-mvp-consultation']


async def _delete_demo_records(tx):
    patients = await tx.patient.find_many(where={'demoKey': {'in': [case['id'] for case in CASES] + LEGACY_DEMO_KEYS}})
    patient_ids = {patient.id for patient in patients}
    consultations = await tx.nutritionconsultation.find_many(
        where={'OR': [{'demoKey': {'in': [case['id'] + '-consultation' for case in CASES] + LEGACY_DEMO_KEYS}},
                      {'patientId': {'in': list(patient_ids)}}]})

    for consultation in consultations:
        generations = await tx.aigeneration.find_many(where={'consultationId': consultation.id})
        for generation in generations:
            await tx.retrievedsource.delete_many(where={'generationId': generation.id})
            await tx.generationplanlink.delete_many(where={'generationId': generation.id})
        await tx.aigeneration.delete_many(where={'consultationId': consultation.id})

        plans = await tx.dietplan.find_many(where={'consultationId': consultation.id})
        for plan in plans:
            await tx.planvalidation.delete_many(where={'dietPlanId': plan.id})
            await tx.dietplanchangelog.delete_many(where={'dietPlanId': plan.id})
            await tx.plannutrientobservation.delete_many(where={'dietPlanId': plan.id})
            meals = await tx.dietplanmeal.find_many(where={'dietPlanId': plan.id})
            for meal in meals:
                await tx.dietplanfood.delete_many(where={'dietPlanMealId': meal.id})
            await tx.dietplanmeal.delete_many(where={'dietPlanId': plan.id})
            await tx.generationplanlink.delete_many(where={'dietPlanId': plan.id})
        await tx.dietplan.delete_many(where={'consultationId': consultation.id})
        calculations = await tx.consultationcalculation.find_many(where={'consultationId': consultation.id})
        for calculation in calculations:
            await tx.calculationmetric.delete_many(where={'calculationId': calculation.id})
        await tx.consultationcalculation.delete_many(where={'consultationId': consultation.id})
        await tx.consultationdietaryitem.delete_many(where={'consultationId': consultation.id})
        await tx.consultationcreaterequest.delete_many(where={'consultationId': consultation.id})
    await tx.nutritionconsultation.delete_many(where={'id': {'in': [consultation.id for consultation in consultations]}})

    for patient in patients:
        await tx.patientdietaryitem.delete_many(where={'patientId': patient.id})
        await tx.patientcondition.delete_many(where={'patientId': patient.id})
        await tx.legacypatientsnapshot.delete_many(where={'patientId': patient.id})
        await tx.patientcreaterequest.delete_many(where={'patientId': patient.id})
    await tx.patient.delete_many(where={'id': {'in': list(patient_ids)}})


async def seed(db):
    async with db.tx() as tx:
        await _delete_demo_records(tx)
        for case in CASES:
            patient = await tx.patient.create(data={
                'demoKey': case['id'], 'name': case['name'], 'age': case['age'], 'sex': case['sex'],
                'ageRecordedAt': datetime.now(timezone.utc),
                'defaultActivityLevel': case['activity'], 'defaultGoal': case['goal'],
                'defaultMealsPerDay': 5,
                'notes': f"Caso de evaluación. Objetivo original: {case['goalCode']}.",
            })
            consultation = await tx.nutritionconsultation.create(data={
                'demoKey': f"{case['id']}-consultation", 'patientId': patient.id,
                'consultationDate': datetime.now(timezone.utc),
                'ageAtConsultation': case['age'], 'sex': case['sex'], 'weightKg': case['weight'],
                'heightM': case['height'], 'activityLevel': case['activity'], 'goal': case['goal'],
                'mealsPerDay': 5,
                'notes': f"Caso de evaluación. Objetivo original: {case['goalCode']}.",
            })
            await tx.consultationdietaryitem.create_many(data=[
                {'consultationId': consultation.id,
                    'kind': 'AVOID', 'content': restriction}
                for restriction in case['restrictions']
            ])
            calculation = await tx.consultationcalculation.create(data={
                'consultationId': consultation.id, 'calculationMethod': 'GROUND_TRUTH',
                'calculationRuleVersion': 'evaluation-fixture-v1',
            })
            await tx.calculationmetric.create_many(data=[
                {'calculationId': calculation.id,
                    'metricCode': METRIC_CODES[key], 'value': value}
                for key, value in case['groundTruth'].items()
            ])
    return [case['id'] for case in CASES]


async def main():
    db = Prisma()
    await db.connect()
    try:
        case_ids = await seed(db)
        print(f'Seed de evaluación reemplazado: {", ".join(case_ids)}.')
    finally:
        await db.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
