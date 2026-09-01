import asyncio
import json
from prisma import Prisma


async def main():
    db = Prisma()
    await db.connect()

    print("🌱 Iniciando el sembrado (seeding) de la base de datos...")

    # Verificamos si ya hay pacientes para no duplicar datos
    count = await db.patient.count()
    if count > 0:
        print("⚠️ La base de datos ya contiene información. Seeding omitido.")
        await db.disconnect()
        return

    # 1. Paciente: María (En revisión)
    await db.patient.create(
        data={
            "name": "María González",
            "age": 28,
            "gender": "female",
            "goal": "Pérdida de peso",
            "pathologies": "Resistencia a la insulina",
            "plans": {
                "create": [{
                    "tdee_calculated": 1850.0,
                    "plan_json": json.dumps({"meals": [{"time": "Desayuno", "items": [{"food": "Avena", "quantity": "1 taza", "calories": 150}]}]}),
                    "status": "EN REVISIÓN"
                }]
            }
        }
    )

    # 2. Paciente: Jorge (Aprobado)
    await db.patient.create(
        data={
            "name": "Jorge Alcántara",
            "age": 41,
            "gender": "male",
            "goal": "Mantenimiento",
            "pathologies": "",
            "plans": {
                "create": [{
                    "tdee_calculated": 2400.0,
                    "plan_json": json.dumps({"meals": []}),
                    "status": "PLAN APROBADO"
                }]
            }
        }
    )

    # 3. Paciente: Lucía (Borrador)
    await db.patient.create(
        data={
            "name": "Lucía Ramírez",
            "age": 34,
            "gender": "female",
            "goal": "Incremento de peso",
            "pathologies": "",
            "plans": {
                "create": [{
                    "tdee_calculated": 2100.0,
                    "plan_json": json.dumps({"meals": []}),
                    "status": "BORRADOR"
                }]
            }
        }
    )

    print("✅ ¡Base de datos sembrada con éxito con pacientes de prueba!")
    await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
