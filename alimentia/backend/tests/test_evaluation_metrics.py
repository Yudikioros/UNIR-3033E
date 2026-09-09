"""Pruebas del servicio de métricas de evaluación por caso (Fase 6, Parte C)."""
import unittest
from uuid import uuid4

from test_plan_management import FakeLLMClient, PlanManagementTestBase, _plan_json
from app.repositories import plan_management as pm
from app.schemas.plan_management import RegenerateRequest


class EvaluationMetricsTests(PlanManagementTestBase):
    async def test_metrics_inexistente_404(self):
        response = await self.client.get(f'plans/{uuid4()}/evaluation-metrics')
        self.assertEqual(response.status_code, 404)

    async def test_metrics_caso_simple_una_version(self):
        consultation, result = await self.draft_plan()
        response = await self.client.get(f"plans/{result.dietPlanId}/evaluation-metrics")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()

        self.assertEqual(body['consultationId'], consultation['id'])
        self.assertEqual(body['planId'], result.dietPlanId)
        self.assertEqual(body['generationCount'], 1)
        self.assertEqual(body['regenerationCount'], 0)
        self.assertEqual(body['manualEditCount'], 0)
        self.assertEqual(body['versionCount'], 1)
        self.assertEqual(body['initialPlanVersion'], 1)
        self.assertEqual(body['finalPlanVersion'], 1)
        self.assertIsNone(body['approvedVersion'])
        self.assertIsNotNone(body['generationDurationMs'])
        self.assertEqual(body['modelName'], 'fake-model')
        self.assertEqual(body['calculationRuleVersion'], '1.0')
        self.assertEqual(body['finalMealCount'], 1)

    async def test_metrics_cuenta_regeneraciones_y_versiones(self):
        consultation, result = await self.draft_plan()
        second = await pm.regenerate_plan(self.db, result.dietPlanId, RegenerateRequest(actor='dra-lopez'),
            llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1)))

        response = await self.client.get(f"plans/{second.dietPlanId}/evaluation-metrics")
        body = response.json()
        self.assertEqual(body['versionCount'], 2)
        self.assertEqual(body['initialPlanVersion'], 1)
        self.assertEqual(body['finalPlanVersion'], 2)
        self.assertEqual(body['regenerationCount'], 1)
        self.assertEqual(body['generationCount'], 2)

    async def test_metrics_desviacion_energetica_y_aprobacion(self):
        # draft_plan() por defecto usa exactamente targetCalories: 0% de desviación real.
        consultation, result = await self.draft_plan()
        approved = await self.client.post(f"plans/{result.dietPlanId}/approve", json={'actor': 'dra-lopez'})
        self.assertEqual(approved.status_code, 200, approved.text)

        response = await self.client.get(f"plans/{result.dietPlanId}/evaluation-metrics")
        body = response.json()
        self.assertEqual(body['approvedVersion'], 1)
        self.assertIsNotNone(body['finalEnergyDeviationPercent'])
        self.assertEqual(body['finalBlockingValidationCount'], 0)
        self.assertIsNotNone(body['timeFromFirstGenerationToApprovalSeconds'])
        self.assertGreaterEqual(body['timeFromFirstGenerationToApprovalSeconds'], 0)

    async def test_metrics_cuenta_ediciones_manuales(self):
        consultation, result = await self.draft_plan()
        edit = {'meals': [{'mealType': 'Comida 1', 'name': 'Editada', 'foods': [
            {'foodName': 'Alimento editado', 'quantity': 1, 'unit': 'g', 'calories': 100}]}]}
        edited = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(edited.status_code, 200, edited.text)

        response = await self.client.get(f"plans/{result.dietPlanId}/evaluation-metrics")
        body = response.json()
        self.assertEqual(body['manualEditCount'], 1)


if __name__ == '__main__':
    unittest.main()
