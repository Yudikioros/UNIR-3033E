"""Pruebas del ciclo de vida human-in-the-loop del plan (Fase 5). El LLM se mockea."""
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI
from prisma import Prisma

from app.repositories import plan_management as pm
from app.routes.capture import router as capture_router
from app.routes.plans import router as plans_router
from app.schemas.generation import GeneratedDietPlan
from app.schemas.plan_management import RegenerateRequest
from app.services import diet_plan_generation
from test_persistence import apply_sql


class FakeLLMClient:
    provider_name = 'fake'
    model = 'fake-model'

    def __init__(self, plan=None, error=None):
        self.plan = plan
        self.error = error
        self.last_user_prompt = None

    async def generate_structured(self, *, system_prompt, user_prompt, response_model, temperature=0.2):
        self.last_user_prompt = user_prompt
        if self.error:
            raise self.error
        return self.plan, 'raw-output-de-prueba'


def _plan_json(meals_per_day=1, calories_each=1000.0):
    return GeneratedDietPlan.model_validate({
        'summary': 'Borrador de prueba',
        'meals': [{'mealType': f'Comida {i+1}', 'name': f'Comida {i+1}', 'foods': [
            {'foodName': f'Alimento {i+1}', 'quantity': 1, 'unit': 'porción',
             'calories': calories_each, 'protein': 10.0, 'carbohydrates': 20.0, 'fat': 5.0},
        ]} for i in range(meals_per_day)],
        'recommendations': [],
    })


class PlanManagementTestBase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'plan_management.db'
        apply_sql(self.path)
        self.db = Prisma(datasource={'url': 'file:' + self.path.as_posix()})
        await self.db.connect()
        self.app = FastAPI()
        self.app.state.db = self.db
        self.app.include_router(capture_router)
        self.app.include_router(plans_router)
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
            'activityLevel': 'moderate', 'goal': 'WEIGHT_LOSS', 'mealsPerDay': 1, **changes}
        response = await self.client.post(f"patients/{patient['id']}/consultations", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def calculated_consultation(self, **changes):
        consultation = await self.consultation(**changes)
        response = await self.client.post(f"consultations/{consultation['id']}/calculate")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def draft_plan(self, target_calories=None, **consultation_changes):
        """Consulta calculada + un DietPlan v1 en DRAFT vía LLM mockeado."""
        consultation = await self.calculated_consultation(**consultation_changes)
        calories = target_calories if target_calories is not None else consultation['targetCalories']
        result = await diet_plan_generation.generate_draft(self.db, consultation['id'],
            llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1, calories_each=calories)))
        return consultation, result


class PlanRetrievalTests(PlanManagementTestBase):
    async def test_get_plan_inexistente_404(self):
        response = await self.client.get(f'plans/{uuid4()}')
        self.assertEqual(response.status_code, 404)

    async def test_get_plan_detalle_completo(self):
        consultation, result = await self.draft_plan()
        response = await self.client.get(f"plans/{result.dietPlanId}")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['status'], 'DRAFT')
        self.assertEqual(body['version'], 1)
        self.assertEqual(body['targetCalories'], consultation['targetCalories'])
        self.assertTrue(body['isEditable'])
        self.assertEqual(body['modelProvider'], 'fake')
        self.assertIn('validations', body)
        self.assertIn('sources', body)

    async def test_get_consultation_plans_inexistente_404(self):
        response = await self.client.get(f'consultations/{uuid4()}/plans')
        self.assertEqual(response.status_code, 404)

    async def test_get_consultation_plans_lista_version_unica(self):
        consultation, result = await self.draft_plan()
        response = await self.client.get(f"consultations/{consultation['id']}/plans")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]['version'], 1)


class PlanEditTests(PlanManagementTestBase):
    async def test_editar_nombre_de_comida(self):
        _consultation, result = await self.draft_plan()
        plan = await self.client.get(f"plans/{result.dietPlanId}")
        meal = plan.json()['meals'][0]
        edit = {'meals': [{'mealType': meal['mealType'], 'name': 'Nombre editado',
            'foods': [{'foodName': f['foodName'], 'quantity': f['quantity'], 'unit': f['unit'],
                       'calories': f['calories'], 'protein': f['protein'],
                       'carbohydrates': f['carbohydrates'], 'fat': f['fat']} for f in meal['foods']]}],
            'actor': 'dra-prueba'}
        response = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['meals'][0]['name'], 'Nombre editado')
        self.assertEqual(response.json()['status'], 'UNDER_REVIEW')

    async def test_editar_alimento_cantidad_y_unidad(self):
        _consultation, result = await self.draft_plan()
        edit = {'meals': [{'mealType': 'Comida 1', 'name': 'Comida 1', 'foods': [
            {'foodName': 'Alimento 1', 'quantity': 250, 'unit': 'g',
             'calories': 1000, 'protein': 10, 'carbohydrates': 20, 'fat': 5}]}]}
        response = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(response.status_code, 200, response.text)
        food = response.json()['meals'][0]['foods'][0]
        self.assertEqual(food['quantity'], 250)
        self.assertEqual(food['unit'], 'g')

    async def test_agregar_y_eliminar_alimentos(self):
        _consultation, result = await self.draft_plan()
        edit = {'meals': [{'mealType': 'Comida 1', 'name': 'Comida 1', 'foods': [
            {'foodName': 'Alimento nuevo A', 'quantity': 1, 'unit': 'pieza', 'calories': 300},
            {'foodName': 'Alimento nuevo B', 'quantity': 1, 'unit': 'pieza', 'calories': 400},
        ]}]}
        response = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(response.status_code, 200, response.text)
        foods = response.json()['meals'][0]['foods']
        self.assertEqual(len(foods), 2)
        self.assertEqual(await self.db.dietplanfood.count(), 2)

    async def test_agregar_y_eliminar_comidas(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1, target_calories=500)
        edit = {'meals': [
            {'mealType': 'Desayuno', 'name': 'Desayuno', 'foods': [
                {'foodName': 'Avena', 'quantity': 1, 'unit': 'taza', 'calories': 250}]},
            {'mealType': 'Comida', 'name': 'Comida', 'foods': [
                {'foodName': 'Pollo', 'quantity': 150, 'unit': 'g', 'calories': 250}]},
        ]}
        response = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()['meals']), 2)
        self.assertEqual(await self.db.dietplanmeal.count(), 2)

    async def test_edicion_registra_auditoria(self):
        _consultation, result = await self.draft_plan()
        edit = {'meals': [{'mealType': 'Comida 1', 'name': 'Nombre nuevo', 'foods': [
            {'foodName': 'Alimento 1', 'quantity': 100, 'unit': 'g', 'calories': 1000}]}],
            'actor': 'dra-lopez'}
        response = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(response.status_code, 200, response.text)
        changes = await self.db.dietplanchangelog.find_many(where={'dietPlanId': result.dietPlanId})
        self.assertTrue(any(c.changeType == 'MANUAL_EDIT' for c in changes))
        self.assertTrue(all(c.changedBy == 'dra-lopez' for c in changes if c.changeType == 'MANUAL_EDIT'))
        name_change = next(c for c in changes if c.field == 'meals[0].name')
        self.assertEqual(name_change.previousValue, 'Comida 1')
        self.assertEqual(name_change.newValue, 'Nombre nuevo')

    async def test_edicion_usa_actor_por_defecto_si_no_se_indica(self):
        _consultation, result = await self.draft_plan()
        edit = {'meals': [{'mealType': 'Comida 1', 'name': 'X', 'foods': [
            {'foodName': 'Alimento 1', 'quantity': 100, 'unit': 'g', 'calories': 1000}]}]}
        response = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(response.status_code, 200, response.text)
        changes = await self.db.dietplanchangelog.find_many(where={'dietPlanId': result.dietPlanId})
        self.assertTrue(all(c.changedBy != 'Nutriólogo' for c in changes))
        self.assertTrue(any(c.changedBy for c in changes))

    async def test_edicion_revalida_totales_y_validaciones(self):
        consultation, result = await self.draft_plan()
        target = consultation['targetCalories']
        # Edita para quedar muy fuera de tolerancia energética.
        edit = {'meals': [{'mealType': 'Comida 1', 'name': 'Comida 1', 'foods': [
            {'foodName': 'Alimento 1', 'quantity': 1, 'unit': 'porción', 'calories': target * 3,
             'protein': 10, 'carbohydrates': 20, 'fat': 5}]}]}
        response = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(response.status_code, 200, response.text)
        codes = {v['code'] for v in response.json()['validations']}
        self.assertIn('ENERGY_OUT_OF_TOLERANCE', codes)
        obs = await self.db.plannutrientobservation.find_many(where={'dietPlanId': result.dietPlanId})
        total = next(o for o in obs if o.metricCode == 'totalCalories')
        # plan_totals redondea a 1 decimal (mismo criterio que Fase 4).
        self.assertAlmostEqual(total.value, target * 3, places=1)

    async def test_editar_plan_inexistente_404(self):
        response = await self.client.patch(f'plans/{uuid4()}', json={'meals': [
            {'mealType': 'X', 'name': 'X', 'foods': [{'foodName': 'A', 'quantity': 1, 'unit': 'g'}]}]})
        self.assertEqual(response.status_code, 404)

    async def test_conflicto_de_concurrencia_en_edicion(self):
        _consultation, result = await self.draft_plan()
        plan = (await self.client.get(f"plans/{result.dietPlanId}")).json()
        edit = {'meals': [{'mealType': 'Comida 1', 'name': 'X', 'foods': [
            {'foodName': 'Alimento 1', 'quantity': 1, 'unit': 'g', 'calories': 100}]}],
            'expectedUpdatedAt': '2000-01-01T00:00:00Z'}
        response = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(response.status_code, 409)


class PlanApprovalTests(PlanManagementTestBase):
    async def test_aprobar_plan_valido(self):
        consultation, result = await self.draft_plan(mealsPerDay=1)
        response = await self.client.post(f"plans/{result.dietPlanId}/approve", json={'actor': 'dra-lopez'})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['status'], 'APPROVED')
        self.assertEqual(body['approvedBy'], 'dra-lopez')
        self.assertIsNotNone(body['approvedAt'])
        changes = await self.db.dietplanchangelog.find_many(where={'dietPlanId': result.dietPlanId})
        self.assertTrue(any(c.changeType == 'APPROVAL' for c in changes))

    async def test_aprobacion_bloqueada_persiste_la_revalidacion(self):
        """La revalidación de la sección 12 debe quedar guardada incluso cuando la
        aprobación en sí se rechaza con 409 (no debe revertirse junto con el 409)."""
        _consultation, result = await self.draft_plan(mealsPerDay=3)
        before = await self.db.planvalidation.find_many(where={'dietPlanId': result.dietPlanId})
        response = await self.client.post(f"plans/{result.dietPlanId}/approve", json={})
        self.assertEqual(response.status_code, 409)
        after = await self.db.planvalidation.find_many(where={'dietPlanId': result.dietPlanId})
        self.assertTrue(any(v.code == 'MEAL_COUNT_MISMATCH' and v.isBlocking for v in after))
        # La revalidación reemplazó el juego de validaciones (no simplemente lo dejó como estaba).
        self.assertNotEqual({v.id for v in before}, {v.id for v in after})

    async def test_aprobar_plan_con_blocking_devuelve_409_con_detalle(self):
        # mealsPerDay=1 en la consulta, pero el borrador (vía draft_plan) también genera 1
        # comida, así que fuerzo el mismatch generando 1 comida contra mealsPerDay=3.
        consultation, result = await self.draft_plan(mealsPerDay=3)
        response = await self.client.post(f"plans/{result.dietPlanId}/approve", json={})
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertIn('blockingValidations', body)
        self.assertTrue(len(body['blockingValidations']) > 0)
        self.assertTrue(any(v['code'] == 'MEAL_COUNT_MISMATCH' for v in body['blockingValidations']))

    async def test_aprobar_plan_inexistente_404(self):
        response = await self.client.post(f'plans/{uuid4()}/approve', json={})
        self.assertEqual(response.status_code, 404)

    async def test_aprobar_plan_ya_aprobado_409(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        first = await self.client.post(f"plans/{result.dietPlanId}/approve", json={})
        self.assertEqual(first.status_code, 200, first.text)
        second = await self.client.post(f"plans/{result.dietPlanId}/approve", json={})
        self.assertEqual(second.status_code, 409)

    async def test_plan_aprobado_no_usa_actor_generico_hardcodeado(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        response = await self.client.post(f"plans/{result.dietPlanId}/approve", json={})
        self.assertNotEqual(response.json()['approvedBy'], 'Nutriólogo')


class PlanImmutabilityTests(PlanManagementTestBase):
    async def _approved_plan(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        approved = await self.client.post(f"plans/{result.dietPlanId}/approve", json={})
        self.assertEqual(approved.status_code, 200, approved.text)
        return result

    async def test_no_se_puede_editar_plan_aprobado(self):
        result = await self._approved_plan()
        edit = {'meals': [{'mealType': 'X', 'name': 'X', 'foods': [
            {'foodName': 'A', 'quantity': 1, 'unit': 'g', 'calories': 100}]}]}
        response = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(response.status_code, 409)

    async def test_no_se_puede_rechazar_plan_aprobado(self):
        result = await self._approved_plan()
        response = await self.client.post(f"plans/{result.dietPlanId}/reject", json={'reason': 'motivo'})
        self.assertEqual(response.status_code, 409)

    async def test_no_se_puede_regenerar_desde_plan_aprobado(self):
        result = await self._approved_plan()
        response = await self.client.post(f"plans/{result.dietPlanId}/regenerate", json={})
        self.assertEqual(response.status_code, 409)

    async def test_aprobado_permanece_intacto_tras_intento_de_edicion(self):
        result = await self._approved_plan()
        before = (await self.client.get(f"plans/{result.dietPlanId}")).json()
        edit = {'meals': [{'mealType': 'X', 'name': 'X', 'foods': [
            {'foodName': 'A', 'quantity': 1, 'unit': 'g', 'calories': 100}]}]}
        await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        after = (await self.client.get(f"plans/{result.dietPlanId}")).json()
        self.assertEqual(before['meals'], after['meals'])
        self.assertEqual(after['status'], 'APPROVED')


class PlanRejectionTests(PlanManagementTestBase):
    async def test_rechazar_plan_requiere_motivo(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        response = await self.client.post(f"plans/{result.dietPlanId}/reject", json={})
        self.assertEqual(response.status_code, 422)

    async def test_rechazar_plan_valido(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        response = await self.client.post(f"plans/{result.dietPlanId}/reject",
            json={'reason': 'No respeta las preferencias del paciente.', 'actor': 'dra-lopez'})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['status'], 'REJECTED')
        self.assertEqual(body['rejectedBy'], 'dra-lopez')
        self.assertEqual(body['rejectionReason'], 'No respeta las preferencias del paciente.')
        changes = await self.db.dietplanchangelog.find_many(where={'dietPlanId': result.dietPlanId})
        self.assertTrue(any(c.changeType == 'REJECTION' for c in changes))

    async def test_plan_rechazado_no_se_convierte_en_draft(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        await self.client.post(f"plans/{result.dietPlanId}/reject", json={'reason': 'motivo'})
        plan = (await self.client.get(f"plans/{result.dietPlanId}")).json()
        self.assertEqual(plan['status'], 'REJECTED')
        self.assertFalse(plan['isEditable'])

    async def test_rechazar_plan_inexistente_404(self):
        response = await self.client.post(f'plans/{uuid4()}/reject', json={'reason': 'motivo'})
        self.assertEqual(response.status_code, 404)


class PlanRegenerationTests(PlanManagementTestBase):
    async def test_regenerar_crea_v2_y_conserva_v1(self):
        consultation, result = await self.draft_plan(mealsPerDay=1)
        second = await pm.regenerate_plan(self.db, result.dietPlanId,
            _regen_dto(), llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1)))
        self.assertEqual(second.version, 2)
        self.assertNotEqual(second.dietPlanId, result.dietPlanId)
        v1 = await self.client.get(f"plans/{result.dietPlanId}")
        self.assertEqual(v1.json()['status'], 'DRAFT')
        self.assertEqual(await self.db.dietplan.count(where={'consultationId': consultation['id']}), 2)

    async def test_regenerar_registra_solicitud_en_auditoria_del_plan_anterior(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        await pm.regenerate_plan(self.db, result.dietPlanId,
            _regen_dto(instructions='Evitar lácteos', actor='dra-lopez'),
            llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1)))
        changes = await self.db.dietplanchangelog.find_many(where={'dietPlanId': result.dietPlanId})
        entry = next(c for c in changes if c.changeType == 'REGENERATION_REQUESTED')
        self.assertEqual(entry.changedBy, 'dra-lopez')
        self.assertEqual(entry.previousValue, '1')
        self.assertEqual(entry.newValue, '2')

    async def test_instrucciones_adicionales_no_cambian_los_calculos(self):
        consultation, result = await self.draft_plan(mealsPerDay=1)
        fake_client = FakeLLMClient(plan=_plan_json(meals_per_day=1))
        await pm.regenerate_plan(self.db, result.dietPlanId,
            _regen_dto(instructions='Usar preparaciones más sencillas'), llm_client=fake_client)
        self.assertIn(f"Target energy: {consultation['targetCalories']} kcal", fake_client.last_user_prompt)
        self.assertIn('Usar preparaciones más sencillas', fake_client.last_user_prompt)
        self.assertIn('son datos del usuario, NO', fake_client.last_user_prompt)

    async def test_regenerar_desde_rechazado_es_valido(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        await self.client.post(f"plans/{result.dietPlanId}/reject", json={'reason': 'motivo'})
        second = await pm.regenerate_plan(self.db, result.dietPlanId,
            _regen_dto(), llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1)))
        self.assertEqual(second.version, 2)
        self.assertEqual(second.status, 'SUCCESS')

    async def test_regenerar_plan_inexistente_404(self):
        response = await self.client.post(f'plans/{uuid4()}/regenerate', json={})
        self.assertEqual(response.status_code, 404)

    async def test_version_nunca_se_reutiliza_tras_multiples_regeneraciones(self):
        consultation, result = await self.draft_plan(mealsPerDay=1)
        v2 = await pm.regenerate_plan(self.db, result.dietPlanId, _regen_dto(),
            llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1)))
        v3 = await pm.regenerate_plan(self.db, v2.dietPlanId, _regen_dto(),
            llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1)))
        versions = sorted(p.version for p in await self.db.dietplan.find_many(
            where={'consultationId': consultation['id']}))
        self.assertEqual(versions, [1, 2, 3])


def _regen_dto(instructions=None, actor=None):
    return RegenerateRequest(instructions=instructions, actor=actor)


class DataIntegrityTests(PlanManagementTestBase):
    async def test_ciclo_completo_no_crea_paciente_ni_consulta_extra(self):
        consultation, result = await self.draft_plan(mealsPerDay=1)
        self.assertEqual(await self.db.patient.count(), 1)
        self.assertEqual(await self.db.nutritionconsultation.count(), 1)
        edit = {'meals': [{'mealType': 'Comida 1', 'name': 'X', 'foods': [
            {'foodName': 'A', 'quantity': 1, 'unit': 'g', 'calories': 100}]}]}
        await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        await pm.regenerate_plan(self.db, result.dietPlanId, _regen_dto(),
            llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1)))
        self.assertEqual(await self.db.patient.count(), 1)
        self.assertEqual(await self.db.nutritionconsultation.count(), 1)


if __name__ == '__main__':
    unittest.main()
