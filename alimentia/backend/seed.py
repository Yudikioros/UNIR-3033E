"""Explicit, separate MVP demo. Existing clinical records are never matched by name."""
import asyncio
from datetime import datetime, timezone
from prisma import Prisma

PATIENT_KEY = 'phase1-maria-mvp'
CONSULTATION_KEY = 'phase1-maria-mvp-consultation'


async def seed(db):
    async with db.tx() as tx:
        patient = await tx.patient.upsert(
            where={'demoKey': PATIENT_KEY},
            data={'create': {
                'demoKey': PATIENT_KEY, 'name': 'María González', 'age': 28, 'sex': 'female',
                'ageRecordedAt': datetime.now(timezone.utc),
                'defaultActivityLevel': 'moderate', 'defaultGoal': 'WEIGHT_LOSS',
                'defaultMealsPerDay': 5,
                'notes': 'Caso de demostración MVP separado del registro histórico. Sin patologías declaradas. Presupuesto: $120–$160 MXN.',
            }, 'update': {}},
        )
        consultation = await tx.nutritionconsultation.upsert(
            where={'demoKey': CONSULTATION_KEY},
            data={'create': {
                'demoKey': CONSULTATION_KEY, 'patientId': patient.id,
                'consultationDate': datetime(2026, 9, 5, tzinfo=timezone.utc),
                'ageAtConsultation': 28, 'sex': 'female', 'weightKg': 68.0, 'heightM': 1.65,
                'activityLevel': 'moderate', 'goal': 'WEIGHT_LOSS', 'mealsPerDay': 5,
                'budgetMin': 120.0, 'budgetMax': 160.0,
                'calculations': {'create': [{'calculationMethod': 'MIFFLIN_ST_JEOR'}]},
                'notes': 'Caso ficticio MVP sin patologías declaradas; todavía sin cálculos ni plan.',
            }, 'update': {}},
        )
    return patient.id, consultation.id


async def main():
    db = Prisma()
    await db.connect()
    try:
        patient_id, consultation_id = await seed(db)
        print(f'Seed MVP disponible: patient={patient_id}, consultation={consultation_id}. No se modificaron registros históricos.')
    finally:
        await db.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
