"""
Pruebas del resumen operativo (`/`). Cada métrica se construye a través del
ciclo de vida REAL del plan (generar/aprobar/rechazar/regenerar vía los
endpoints existentes, LLM mockeado) para verificar que las definiciones
exactas del pedido -última versión por consulta, timestamps reales,
desempates determinísticos- se cumplen contra datos genuinos, no contra
fixtures artificiales que ya asuman el resultado.
"""
import unittest
from datetime import datetime, timedelta, timezone

from app.repositories import plan_management as pm
from app.routes.dashboard import router as dashboard_router
from app.schemas.plan_management import RegenerateRequest
from app.services import diet_plan_generation
from test_plan_management import FakeLLMClient, PlanManagementTestBase, _plan_json


def _regen_dto(instructions=None, actor=None):
    return RegenerateRequest(instructions=instructions, actor=actor)


async def _generate(db, consultation):
    """Genera un plan directamente sobre una consulta ya calculada, sin pasar
    por otro paciente nuevo (a diferencia de `draft_plan`, que siempre crea
    uno) -útil cuando el paciente ya existe con más de una consulta."""
    return await diet_plan_generation.generate_draft(
        db, consultation['id'],
        llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1, calories_each=consultation['targetCalories'])))


class DashboardTestBase(PlanManagementTestBase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.app.include_router(dashboard_router)

    async def summary(self):
        response = await self.client.get('dashboard/summary')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def patient_row(self, body, patient_id):
        return next(row for row in body['recentPatients'] if row['id'] == patient_id)


class MetricsTests(DashboardTestBase):
    async def test_pacientes_registrados_no_cuenta_consultas_ni_planes(self):
        await self.patient(name='Sin consulta')
        p2 = await self.patient(name='Con varias consultas y planes')
        await self.draft_plan(patient=p2)

        body = await self.summary()
        self.assertEqual(body['metrics']['registeredPatients'], 2)

    async def test_planes_generados_cuenta_todas_las_versiones(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        await pm.regenerate_plan(self.db, result.dietPlanId, _regen_dto(),
            llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1)))

        body = await self.summary()
        self.assertEqual(body['metrics']['generatedPlans'], 2)

    async def test_pendientes_y_aprobados_usan_solo_la_ultima_version(self):
        # A: v1 DRAFT sin resolver -> pendiente.
        await self.draft_plan(mealsPerDay=1)
        # B: v1 DRAFT -> aprobado -> aprobado.
        _c_b, r_b = await self.draft_plan(mealsPerDay=1)
        approved = await self.client.post(f"plans/{r_b.dietPlanId}/approve", json={})
        self.assertEqual(approved.status_code, 200, approved.text)
        # C: v1 DRAFT -> rechazado -> ni pendiente ni aprobado (última versión = REJECTED).
        _c_c, r_c = await self.draft_plan(mealsPerDay=1)
        rejected = await self.client.post(f"plans/{r_c.dietPlanId}/reject", json={'reason': 'motivo de prueba'})
        self.assertEqual(rejected.status_code, 200, rejected.text)
        # D: v1 DRAFT -> rechazado -> regenerado a v2 DRAFT -> pendiente (v1 es histórico).
        _c_d, r_d = await self.draft_plan(mealsPerDay=1)
        await self.client.post(f"plans/{r_d.dietPlanId}/reject", json={'reason': 'motivo de prueba'})
        v2 = await pm.regenerate_plan(self.db, r_d.dietPlanId, _regen_dto(),
            llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1)))
        self.assertEqual(v2.status, 'SUCCESS')

        body = await self.summary()
        self.assertEqual(body['metrics']['pendingReview'], 2)  # A y D
        self.assertEqual(body['metrics']['approvedPlans'], 1)  # B

    async def test_draft_historico_mas_approved_actual_cuenta_como_aprobado(self):
        """v1 DRAFT (histórico, nunca resuelto) -> regenerado a v2 -> v2 aprobado.
        La consulta debe contar como aprobada, no como pendiente por v1."""
        consultation, r1 = await self.draft_plan(mealsPerDay=1)
        r2 = await pm.regenerate_plan(self.db, r1.dietPlanId, _regen_dto(),
            llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1, calories_each=consultation['targetCalories'])))
        approved = await self.client.post(f"plans/{r2.dietPlanId}/approve", json={})
        self.assertEqual(approved.status_code, 200, approved.text)

        v1 = await self.db.dietplan.find_unique(where={'id': r1.dietPlanId})
        self.assertEqual(v1.status, 'DRAFT')  # v1 nunca se tocó

        body = await self.summary()
        self.assertEqual(body['metrics']['pendingReview'], 0)
        self.assertEqual(body['metrics']['approvedPlans'], 1)

    async def test_approved_historico_mas_draft_actual_no_cuenta_como_aprobado(self):
        """Caso legado/imposible vía endpoints reales (aprobar bloquea
        regenerar): se construye directamente en DB para probar que la
        agregación usa SIEMPRE la última versión, sin excepciones."""
        _consultation, r1 = await self.draft_plan(mealsPerDay=1)
        approved = await self.client.post(f"plans/{r1.dietPlanId}/approve", json={})
        self.assertEqual(approved.status_code, 200, approved.text)
        v1 = await self.db.dietplan.find_unique(where={'id': r1.dietPlanId})
        await self.db.dietplan.create(data={
            'consultationId': v1.consultationId, 'version': 2, 'status': 'DRAFT',
        })

        body = await self.summary()
        self.assertEqual(body['metrics']['pendingReview'], 1)
        self.assertEqual(body['metrics']['approvedPlans'], 0)
        # Tampoco debe colarse en el promedio de tiempo de revisión: la
        # última versión ya no está aprobada.
        self.assertIsNone(body['metrics']['averageReviewTimeSeconds'])


class AverageReviewTimeTests(DashboardTestBase):
    async def test_sin_planes_aprobados_es_null(self):
        await self.draft_plan(mealsPerDay=1)
        body = await self.summary()
        self.assertIsNone(body['metrics']['averageReviewTimeSeconds'])

    async def test_promedio_usa_timestamps_reales_de_generacion_y_aprobacion(self):
        """Se controla directamente `AIGeneration.createdAt` y
        `DietPlan.approvedAt` para verificar el cálculo exacto -no basta con
        confirmar que el valor "existe", se comprueba la aritmética real."""
        _c1, r1 = await self.draft_plan(mealsPerDay=1)
        await self.client.post(f"plans/{r1.dietPlanId}/approve", json={})
        _c2, r2 = await self.draft_plan(mealsPerDay=1)
        await self.client.post(f"plans/{r2.dietPlanId}/approve", json={})

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        link1 = await self.db.generationplanlink.find_first(where={'dietPlanId': r1.dietPlanId})
        link2 = await self.db.generationplanlink.find_first(where={'dietPlanId': r2.dietPlanId})
        await self.db.aigeneration.update(where={'id': link1.generationId}, data={'createdAt': base})
        await self.db.aigeneration.update(where={'id': link2.generationId}, data={'createdAt': base})
        await self.db.dietplan.update(where={'id': r1.dietPlanId}, data={'approvedAt': base + timedelta(seconds=600)})
        await self.db.dietplan.update(where={'id': r2.dietPlanId}, data={'approvedAt': base + timedelta(seconds=1200)})

        body = await self.summary()
        # promedio de 600s y 1200s = 900s
        self.assertAlmostEqual(body['metrics']['averageReviewTimeSeconds'], 900.0, delta=1.0)

    async def test_timestamps_inconsistentes_negativos_se_excluyen(self):
        _c1, r1 = await self.draft_plan(mealsPerDay=1)
        await self.client.post(f"plans/{r1.dietPlanId}/approve", json={})
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        link1 = await self.db.generationplanlink.find_first(where={'dietPlanId': r1.dietPlanId})
        # generatedAt POSTERIOR a approvedAt: inconsistente, debe excluirse.
        await self.db.aigeneration.update(where={'id': link1.generationId}, data={'createdAt': base + timedelta(seconds=100)})
        await self.db.dietplan.update(where={'id': r1.dietPlanId}, data={'approvedAt': base})

        body = await self.summary()
        self.assertIsNone(body['metrics']['averageReviewTimeSeconds'])


class RecentPatientsTests(DashboardTestBase):
    async def test_paciente_sin_consulta(self):
        patient = await self.patient(name='Sin ninguna consulta')
        body = await self.summary()
        row = self.patient_row(body, patient['id'])
        self.assertIsNone(row['goal'])
        self.assertIsNone(row['latestConsultationDate'])
        self.assertIsNone(row['latestPlanStatus'])
        self.assertIsNone(row['latestPlanId'])

    async def test_consulta_sin_plan(self):
        consultation = await self.calculated_consultation()
        patient_id = consultation['patientId']
        body = await self.summary()
        row = self.patient_row(body, patient_id)
        self.assertIsNotNone(row['latestConsultationDate'])
        self.assertIsNone(row['latestPlanStatus'])
        self.assertIsNone(row['latestPlanId'])

    async def test_objetivo_es_el_de_la_consulta_no_el_habitual_del_paciente(self):
        patient = await self.patient(name='Con objetivo distinto', defaultGoal='MAINTENANCE')
        await self.consultation(patient=patient, goal='WEIGHT_GAIN')
        body = await self.summary()
        row = self.patient_row(body, patient['id'])
        self.assertEqual(row['goal'], 'WEIGHT_GAIN')

    async def test_estado_muestra_la_ultima_version_de_la_ultima_consulta(self):
        patient = await self.patient(name='Con dos consultas')
        c1 = await self.calculated_consultation(patient=patient, consultationDate='2026-01-01T00:00:00Z')
        await _generate(self.db, c1)
        # Segunda consulta, más reciente, todavía sin plan generado.
        c2 = await self.consultation(patient=patient, consultationDate='2026-06-01T00:00:00Z')

        body = await self.summary()
        row = self.patient_row(body, patient['id'])
        self.assertEqual(row['latestConsultationDate'][:10], '2026-06-01')
        self.assertIsNone(row['latestPlanStatus'])  # la consulta más reciente (c2) no tiene plan
        del c2  # solo se usa para crearla; su contenido no hace falta aquí

    async def test_orden_pacientes_recientes_por_fecha_de_registro(self):
        first = await self.patient(name='Primero registrado')
        second = await self.patient(name='Segundo registrado')
        body = await self.summary()
        ids = [row['id'] for row in body['recentPatients']]
        self.assertLess(ids.index(second['id']), ids.index(first['id']))


class PendingPanelTests(DashboardTestBase):
    async def test_panel_contiene_entradas_reales_con_ids_correctos(self):
        patient = await self.patient(name='Paciente pendiente')
        _consultation, result = await self.draft_plan(patient=patient, mealsPerDay=1)

        body = await self.summary()
        entry = next(item for item in body['pendingPlans'] if item['planId'] == result.dietPlanId)
        self.assertEqual(entry['patientId'], patient['id'])
        self.assertEqual(entry['patientName'], patient['name'])
        self.assertEqual(entry['version'], 1)
        self.assertEqual(entry['status'], 'DRAFT')

    async def test_maximo_del_panel_es_5_pero_el_total_es_real(self):
        for _ in range(7):
            await self.draft_plan(mealsPerDay=1)

        body = await self.summary()
        self.assertEqual(len(body['pendingPlans']), 5)
        self.assertEqual(body['metrics']['pendingReview'], 7)
        self.assertEqual(body['pendingPlansTotal'], 7)

    async def test_sin_pendientes_el_panel_queda_vacio(self):
        body = await self.summary()
        self.assertEqual(body['pendingPlans'], [])
        self.assertEqual(body['metrics']['pendingReview'], 0)


if __name__ == '__main__':
    unittest.main()
