"""Pruebas de trazabilidad completa del plan (Fase 6, Parte B)."""
import unittest
from uuid import uuid4

from test_plan_management import PlanManagementTestBase


class PlanTraceabilityTests(PlanManagementTestBase):
    async def test_traceability_inexistente_404(self):
        response = await self.client.get(f'plans/{uuid4()}/traceability')
        self.assertEqual(response.status_code, 404)

    async def test_traceability_reconstruye_calculo_y_generacion(self):
        consultation, result = await self.draft_plan()
        response = await self.client.get(f"plans/{result.dietPlanId}/traceability")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()

        self.assertEqual(body['plan']['id'], result.dietPlanId)
        self.assertEqual(body['plan']['version'], 1)
        self.assertEqual(body['plan']['status'], 'DRAFT')

        self.assertEqual(body['calculation']['method'], 'MIFFLIN_ST_JEOR')
        self.assertEqual(body['calculation']['rulesetVersion'], '1.0')
        self.assertIsNotNone(body['calculation']['calculationId'])

        self.assertEqual(body['generation']['generationId'], result.generationId)
        self.assertEqual(body['generation']['modelProvider'], 'fake')
        self.assertEqual(body['generation']['modelName'], 'fake-model')
        self.assertIsNotNone(body['generation']['generationDurationMs'])

        self.assertEqual(body['humanReview']['manualEditCount'], 0)
        self.assertEqual(body['humanReview']['regenerationCount'], 0)
        self.assertIsNone(body['humanReview']['approvedAt'])

    async def test_traceability_no_expone_pii_ni_uuid_de_paciente(self):
        """Sección 15: la trazabilidad nunca expone patientId ni datos de identidad."""
        consultation, result = await self.draft_plan()
        response = await self.client.get(f"plans/{result.dietPlanId}/traceability")
        body = response.json()
        serialized = str(body)
        self.assertNotIn(consultation['patientId'], serialized)
        self.assertNotIn('patientId', serialized)
        self.assertEqual(body['generation']['modelName'], 'fake-model')  # sanity: respuesta real, no un stub vacío

    async def test_traceability_cuenta_ediciones_manuales(self):
        consultation, result = await self.draft_plan()
        edit = {'meals': [{'mealType': 'Comida 1', 'name': 'Editada', 'foods': [
            {'foodName': 'Alimento editado', 'quantity': 1, 'unit': 'g', 'calories': 100}]}]}
        edited = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(edited.status_code, 200, edited.text)

        response = await self.client.get(f"plans/{result.dietPlanId}/traceability")
        body = response.json()
        self.assertEqual(body['humanReview']['manualEditCount'], 1)

    async def test_traceability_registra_aprobacion(self):
        consultation, result = await self.draft_plan()
        approved = await self.client.post(f"plans/{result.dietPlanId}/approve", json={'actor': 'dra-lopez'})
        self.assertEqual(approved.status_code, 200, approved.text)

        response = await self.client.get(f"plans/{result.dietPlanId}/traceability")
        body = response.json()
        self.assertEqual(body['plan']['status'], 'APPROVED')
        self.assertEqual(body['humanReview']['approvedBy'], 'dra-lopez')
        self.assertIsNotNone(body['humanReview']['approvedAt'])

    async def test_traceability_fuentes_reales_no_inventadas(self):
        """Sección 16: sin `KnowledgeSource` sincronizado en esta base de prueba aislada,
        ningún `sourceId` puede resolver -> `sources` queda vacío, nunca inventado."""
        consultation, result = await self.draft_plan()
        response = await self.client.get(f"plans/{result.dietPlanId}/traceability")
        body = response.json()
        self.assertEqual(body['sources'], [])
        # Ya no es None: toda generación nueva registra explícitamente si usó RAG.
        self.assertIn(body['resources']['knowledgeBaseUsed'], (True, False))


if __name__ == '__main__':
    unittest.main()
