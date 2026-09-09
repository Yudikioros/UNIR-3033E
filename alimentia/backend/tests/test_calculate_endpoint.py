"""Pruebas HTTP del endpoint POST /api/v1/consultations/{id}/calculate (Fase 3)."""
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI
from prisma import Prisma

from app.routes.capture import router
from seed import seed
from test_persistence import apply_sql


class CalculateEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'calculate.db'
        apply_sql(self.path)
        self.db = Prisma(datasource={'url': 'file:' + self.path.as_posix()})
        await self.db.connect()
        self.app = FastAPI()
        self.app.state.db = self.db
        self.app.include_router(router)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test/api/v1/')

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.db.disconnect()
        self.temp.cleanup()

    async def patient(self, **changes):
        response = await self.client.post('patients', json={'name': 'Test patient', 'sex': 'female', 'age': 28, **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def consultation(self, patient=None, **changes):
        patient = patient or await self.patient()
        payload = {'ageAtConsultation': 28, 'sex': 'female', 'weightKg': 68, 'heightM': 1.65,
            'activityLevel': 'moderate', 'goal': 'WEIGHT_LOSS', 'mealsPerDay': 5, **changes}
        response = await self.client.post(f"patients/{patient['id']}/consultations", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def test_consulta_inexistente_devuelve_404(self):
        response = await self.client.post(f'consultations/{uuid4()}/calculate')
        self.assertEqual(response.status_code, 404)

    async def test_consulta_incompleta_devuelve_422(self):
        patient = await self.patient()
        response = await self.client.post(f"patients/{patient['id']}/consultations", json={})
        self.assertEqual(response.status_code, 201, response.text)
        incomplete = response.json()
        result = await self.client.post(f"consultations/{incomplete['id']}/calculate")
        self.assertEqual(result.status_code, 422)

    async def test_consulta_valida_calcula_y_persiste(self):
        consultation = await self.consultation()
        response = await self.client.post(f"consultations/{consultation['id']}/calculate")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['calculationMethod'], 'MIFFLIN_ST_JEOR')
        self.assertEqual(body['calculationRuleVersion'], '1.0')
        self.assertIsNotNone(body['targetCalories'])
        self.assertIsNotNone(body['bmi'])
        self.assertIsNotNone(body['proteinGrams'])

        # El resultado persiste: una lectura posterior GET refleja el mismo cálculo.
        fetched = await self.client.get(f"consultations/{consultation['id']}")
        self.assertEqual(fetched.json()['targetCalories'], body['targetCalories'])
        self.assertEqual(await self.db.consultationcalculation.count(), 1)
        self.assertEqual(await self.db.calculationmetric.count(), 9)

    async def test_recalculo_agrega_historial_sin_sobrescribir(self):
        consultation = await self.consultation()
        first = await self.client.post(f"consultations/{consultation['id']}/calculate")
        second = await self.client.post(f"consultations/{consultation['id']}/calculate")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['targetCalories'], second.json()['targetCalories'])
        # Cada llamada agrega un registro nuevo; no se sobrescribe el historial.
        self.assertEqual(await self.db.consultationcalculation.count(), 2)
        self.assertEqual(await self.db.calculationmetric.count(), 18)

    async def test_calculo_no_crea_paciente_ni_consulta_nueva(self):
        consultation = await self.consultation()
        self.assertEqual(await self.db.patient.count(), 1)
        self.assertEqual(await self.db.nutritionconsultation.count(), 1)
        await self.client.post(f"consultations/{consultation['id']}/calculate")
        self.assertEqual(await self.db.patient.count(), 1)
        self.assertEqual(await self.db.nutritionconsultation.count(), 1)

    async def test_datos_fuera_de_rango_tecnico_devuelve_400(self):
        consultation = await self.consultation(weightKg=500)
        response = await self.client.post(f"consultations/{consultation['id']}/calculate")
        self.assertEqual(response.status_code, 400, response.text)

    async def test_maria_gonzalez_demo_seed_calcula_correctamente(self):
        patient_id, consultation_id = await seed(self.db)
        response = await self.client.post(f"consultations/{consultation_id}/calculate")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()

        expected_bmr = (10 * 68.0) + (6.25 * 165.0) - (5 * 28) - 161
        expected_tdee = expected_bmr * 1.55
        expected_target = expected_tdee - 500

        self.assertAlmostEqual(body['basalMetabolicRate'], round(expected_bmr, 2), places=6)
        self.assertAlmostEqual(body['totalEnergyExpenditure'], round(expected_tdee, 2), places=6)
        self.assertAlmostEqual(body['targetCalories'], round(expected_target, 2), places=6)
        self.assertEqual(body['calculationMethod'], 'MIFFLIN_ST_JEOR')

        # La consulta seed ya traía un registro de cálculo vacío (Fase 1); esta
        # llamada agrega el segundo, ahora con métricas reales.
        self.assertEqual(await self.db.consultationcalculation.count(), 2)
        self.assertEqual(await self.db.patient.count(), 1)
        self.assertEqual(await self.db.nutritionconsultation.count(), 1)


if __name__ == '__main__':
    unittest.main()
