"""
Pruebas del progreso por etapas real durante la generación de un borrador
(corrección de UX). Nunca se depende de Ollama real ni de temporizadores: el
control de en qué punto exacto está la generación se logra reteniendo la
llamada "LLM" (mockeada) con un `asyncio.Event`, exactamente como el backend
real quedaría retenido esperando la respuesta del modelo.
"""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app.repositories import plan_management as pm
from app.schemas.plan_management import RegenerateRequest
from app.services import diet_plan_generation, food_db, rag_engine
from app.services.diet_plan_generation import GenerationStage
from app.services.llm_client import LLMGenerationError
from test_plan_management import FakeLLMClient, PlanManagementTestBase, _plan_json


class GenerationProgressTestBase(PlanManagementTestBase):
    """Aísla cada prueba del BAM.xlsx y de la búsqueda RAG reales que puedan
    existir en este entorno (mismo criterio que test_generate_draft_endpoint.py,
    sección 33 de Fase 5): cada prueba de este archivo ejecuta un pipeline de
    generación completo, y depender del modelo de embeddings real añadiría
    varios segundos por prueba -y resultados no deterministas- sin aportar
    nada a lo que aquí se verifica (el progreso por etapas, no el contenido
    RAG en sí, que ya se prueba en test_generate_draft_endpoint.py)."""
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self._food_db_dir = tempfile.TemporaryDirectory()
        self._env_patch = patch.dict('os.environ',
            {'ALIMENTIA_FOOD_DB_PATH': str(Path(self._food_db_dir.name) / 'BAM.xlsx')})
        self._env_patch.start()
        food_db.reset_food_database_cache()
        self._rag_patch = patch.object(rag_engine.knowledge_base_service, 'search', return_value=[])
        self._rag_patch.start()

    async def asyncTearDown(self):
        self._rag_patch.stop()
        self._env_patch.stop()
        food_db.reset_food_database_cache()
        self._food_db_dir.cleanup()
        await super().asyncTearDown()


class ControllableLLMClient:
    """Como FakeLLMClient, pero `generate_structured` queda bloqueado hasta
    que la prueba libere `release` -así se puede inspeccionar de forma
    determinística el estado exacto de la generación mientras está "en
    curso", sin sleeps arbitrarios ni condiciones de carrera."""
    provider_name = 'fake'
    model = 'fake-model'

    def __init__(self, plan=None, error=None):
        self.plan = plan
        self.error = error
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def generate_structured(self, *, system_prompt, user_prompt, response_model, temperature=0.2):
        self.entered.set()
        await self.release.wait()
        if self.error:
            raise self.error
        return self.plan, 'raw-output-de-prueba'


async def _wait_until_finished(db, generation_id, timeout=5.0):
    async def _poll():
        while True:
            status = await diet_plan_generation.get_generation_status(db, generation_id)
            if status.status != 'IN_PROGRESS':
                return status
            await asyncio.sleep(0.01)
    return await asyncio.wait_for(_poll(), timeout=timeout)


class GenerationProgressTests(GenerationProgressTestBase):
    async def test_estado_inicial_es_in_progress_validating(self):
        consultation = await self.calculated_consultation()
        client = ControllableLLMClient(plan=_plan_json(meals_per_day=1))
        generation_id = await diet_plan_generation.start_generation_job(self.db, consultation['id'], llm_client=client)
        status = await diet_plan_generation.get_generation_status(self.db, generation_id)
        self.assertEqual(status.status, 'IN_PROGRESS')
        self.assertIn(status.stage, (GenerationStage.VALIDATING.value, GenerationStage.LOADING_CALCULATIONS.value,
            GenerationStage.LOADING_FOOD_DATA.value, GenerationStage.SEARCHING_KNOWLEDGE.value,
            GenerationStage.BUILDING_CONTEXT.value, GenerationStage.GENERATING_WITH_LLM.value))
        self.assertIsNone(status.completedAt)
        client.release.set()
        await _wait_until_finished(self.db, generation_id)

    async def test_start_responde_de_inmediato_sin_esperar_al_llm(self):
        """El endpoint /start nunca debe bloquearse esperando la generación
        completa: debe devolver el id de inmediato, mientras la llamada al
        LLM sigue retenida."""
        consultation = await self.calculated_consultation()
        client = ControllableLLMClient(plan=_plan_json(meals_per_day=1))
        generation_id = await diet_plan_generation.start_generation_job(self.db, consultation['id'], llm_client=client)
        self.assertTrue(generation_id)
        # La llamada al LLM todavía no se libera: la generación sigue en curso.
        status = await diet_plan_generation.get_generation_status(self.db, generation_id)
        self.assertEqual(status.status, 'IN_PROGRESS')
        client.release.set()
        await _wait_until_finished(self.db, generation_id)

    async def test_stage_generating_with_llm_activo_durante_la_llamada(self):
        consultation = await self.calculated_consultation()
        client = ControllableLLMClient(plan=_plan_json(meals_per_day=1))
        generation_id = await diet_plan_generation.start_generation_job(self.db, consultation['id'], llm_client=client)
        await asyncio.wait_for(client.entered.wait(), timeout=5)
        status = await diet_plan_generation.get_generation_status(self.db, generation_id)
        self.assertEqual(status.status, 'IN_PROGRESS')
        self.assertEqual(status.stage, GenerationStage.GENERATING_WITH_LLM.value)
        client.release.set()
        final = await _wait_until_finished(self.db, generation_id)
        self.assertEqual(final.status, 'SUCCESS')

    async def test_completed_incluye_dietplanid_y_completedat(self):
        consultation = await self.calculated_consultation()
        client = ControllableLLMClient(plan=_plan_json(meals_per_day=1))
        generation_id = await diet_plan_generation.start_generation_job(self.db, consultation['id'], llm_client=client)
        client.release.set()
        final = await _wait_until_finished(self.db, generation_id)
        self.assertEqual(final.status, 'SUCCESS')
        self.assertEqual(final.stage, GenerationStage.COMPLETED.value)
        self.assertIsNotNone(final.completedAt)
        self.assertIsNotNone(final.dietPlanId)
        plan = await self.db.dietplan.find_unique(where={'id': final.dietPlanId})
        self.assertEqual(plan.status, 'DRAFT')

    async def test_fallo_del_llm_marca_failed_con_mensaje(self):
        consultation = await self.calculated_consultation()
        client = ControllableLLMClient(error=LLMGenerationError('JSON inválido de prueba'))
        generation_id = await diet_plan_generation.start_generation_job(self.db, consultation['id'], llm_client=client)
        client.release.set()
        final = await _wait_until_finished(self.db, generation_id)
        self.assertEqual(final.status, 'FAILED')
        self.assertEqual(final.stage, GenerationStage.FAILED.value)
        self.assertIn('JSON inválido de prueba', final.errorMessage)
        self.assertIsNone(final.dietPlanId)
        self.assertIsNotNone(final.completedAt)
        self.assertEqual(await self.db.dietplan.count(), 0)

    async def test_consulta_sin_calculo_marca_failed_de_inmediato(self):
        consultation = await self.consultation()  # completa, pero sin /calculate
        generation_id = await diet_plan_generation.start_generation_job(
            self.db, consultation['id'], llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1)))
        final = await _wait_until_finished(self.db, generation_id)
        self.assertEqual(final.status, 'FAILED')
        self.assertIn('calcularse', final.errorMessage)

    async def test_status_de_generacion_inexistente_404(self):
        with self.assertRaises(Exception):
            await diet_plan_generation.get_generation_status(self.db, str(uuid4()))

    async def test_generacion_sincrona_es_consultable_via_status(self):
        """La ruta síncrona (generate_draft) y la de progreso comparten la
        misma fila: el id que devuelve sigue siendo consultable después."""
        consultation = await self.calculated_consultation()
        result = await diet_plan_generation.generate_draft(
            self.db, consultation['id'], llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1)))
        status = await diet_plan_generation.get_generation_status(self.db, result.generationId)
        self.assertEqual(status.status, 'SUCCESS')
        self.assertEqual(status.stage, GenerationStage.COMPLETED.value)
        self.assertEqual(status.dietPlanId, result.dietPlanId)

    async def test_endpoint_start_devuelve_generation_id(self):
        consultation = await self.calculated_consultation()
        with self._patch_llm_client(FakeLLMClient(plan=_plan_json(meals_per_day=1))):
            response = await self.client.post(f"consultations/{consultation['id']}/generate-draft/start")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['generationId'])

    async def test_endpoint_status_expone_progreso(self):
        consultation = await self.calculated_consultation()
        with self._patch_llm_client(FakeLLMClient(plan=_plan_json(meals_per_day=1))):
            started = await self.client.post(f"consultations/{consultation['id']}/generate-draft/start")
        generation_id = started.json()['generationId']
        await _wait_until_finished(self.db, generation_id)
        response = await self.client.get(f"generations/{generation_id}/status")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['status'], 'SUCCESS')
        self.assertEqual(body['stage'], 'COMPLETED')
        self.assertTrue(body['dietPlanId'])

    async def test_endpoint_status_generacion_inexistente_404(self):
        response = await self.client.get(f"generations/{uuid4()}/status")
        self.assertEqual(response.status_code, 404)

    def _patch_llm_client(self, fake_client):
        from unittest.mock import patch
        return patch('app.services.diet_plan_generation.LLMClient', return_value=fake_client)


class RegenerationProgressTests(GenerationProgressTestBase):
    async def test_regenerar_con_progreso_registra_auditoria_al_terminar(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        client = ControllableLLMClient(plan=_plan_json(meals_per_day=1))
        generation_id = await pm.start_regeneration_job(self.db, result.dietPlanId,
            RegenerateRequest(instructions='Evitar lácteos', actor='dra-lopez'), llm_client=client)
        # Todavía no hay auditoría: la generación sigue retenida en el LLM.
        pending = await self.db.dietplanchangelog.find_many(
            where={'dietPlanId': result.dietPlanId, 'changeType': 'REGENERATION_REQUESTED'})
        self.assertEqual(pending, [])
        client.release.set()
        final = await _wait_until_finished(self.db, generation_id)
        self.assertEqual(final.status, 'SUCCESS')

        async def _wait_for_changelog():
            while True:
                rows = await self.db.dietplanchangelog.find_many(
                    where={'dietPlanId': result.dietPlanId, 'changeType': 'REGENERATION_REQUESTED'})
                if rows:
                    return rows
                await asyncio.sleep(0.01)
        rows = await asyncio.wait_for(_wait_for_changelog(), timeout=5)
        self.assertEqual(rows[0].changedBy, 'dra-lopez')
        self.assertEqual(rows[0].previousValue, '1')
        self.assertEqual(rows[0].newValue, '2')

    async def test_regenerar_plan_inexistente_404(self):
        with self.assertRaises(Exception) as ctx:
            await pm.start_regeneration_job(self.db, str(uuid4()), RegenerateRequest())
        self.assertEqual(ctx.exception.status, 404)

    async def test_regenerar_plan_aprobado_409(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        await self.client.post(f"plans/{result.dietPlanId}/approve", json={})
        with self.assertRaises(Exception) as ctx:
            await pm.start_regeneration_job(self.db, result.dietPlanId, RegenerateRequest())
        self.assertEqual(ctx.exception.status, 409)

    async def test_no_registra_auditoria_si_la_generacion_falla(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        client = ControllableLLMClient(error=LLMGenerationError('proveedor caído'))
        generation_id = await pm.start_regeneration_job(self.db, result.dietPlanId, RegenerateRequest(), llm_client=client)
        client.release.set()
        final = await _wait_until_finished(self.db, generation_id)
        self.assertEqual(final.status, 'FAILED')
        rows = await self.db.dietplanchangelog.find_many(
            where={'dietPlanId': result.dietPlanId, 'changeType': 'REGENERATION_REQUESTED'})
        self.assertEqual(rows, [])

    async def test_endpoint_regenerate_start(self):
        _consultation, result = await self.draft_plan(mealsPerDay=1)
        with self._patch_llm_client(FakeLLMClient(plan=_plan_json(meals_per_day=1))):
            response = await self.client.post(f"plans/{result.dietPlanId}/regenerate/start", json={})
        self.assertEqual(response.status_code, 200, response.text)
        generation_id = response.json()['generationId']
        await _wait_until_finished(self.db, generation_id)

    def _patch_llm_client(self, fake_client):
        from unittest.mock import patch
        return patch('app.services.diet_plan_generation.LLMClient', return_value=fake_client)


if __name__ == '__main__':
    unittest.main()
