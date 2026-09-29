"""Pruebas de generación de borrador con LLM (Fase 4). El LLM se mockea; nunca se depende del real."""
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import FastAPI
from openpyxl import Workbook
from prisma import Prisma

from app.repositories.capture import CaptureError
from app.repositories.knowledge import sync_knowledge_sources
from app.routes.capture import router
from app.schemas.generation import GeneratedDietPlan
from app.services import diet_plan_generation, food_db, rag_engine
from app.services.llm_client import LLMGenerationError
from test_persistence import apply_sql


def _write_bam(path: Path, rows):
    """BAM.xlsx sintético mínimo con la estructura real (fila 13, columnas con codigomex2)."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'BAM 18.1.1'
    for i in range(1, 13):
        ws.append([f'nota {i}'])
    ws.append(food_db.REQUIRED_COLUMNS)
    for row in rows:
        ws.append(row)
    wb.save(path)

VALID_PLAN = GeneratedDietPlan.model_validate({
    'summary': 'Borrador de prueba',
    'meals': [
        {'mealType': 'Desayuno', 'name': 'Avena con fruta', 'foods': [
            {'foodName': 'Avena', 'quantity': 40, 'unit': 'g', 'calories': 150, 'protein': 5, 'carbohydrates': 27, 'fat': 3}]},
        {'mealType': 'Colación', 'name': 'Fruta', 'foods': [
            {'foodName': 'Manzana', 'quantity': 1, 'unit': 'pieza', 'calories': 95, 'protein': 0, 'carbohydrates': 25, 'fat': 0}]},
        {'mealType': 'Comida', 'name': 'Pollo con verduras', 'foods': [
            {'foodName': 'Pechuga de pollo', 'quantity': 150, 'unit': 'g', 'calories': 250, 'protein': 45, 'carbohydrates': 0, 'fat': 6}]},
        {'mealType': 'Colación', 'name': 'Yogur', 'foods': [
            {'foodName': 'Yogur natural', 'quantity': 200, 'unit': 'ml', 'calories': 120, 'protein': 8, 'carbohydrates': 12, 'fat': 4}]},
        {'mealType': 'Cena', 'name': 'Ensalada con atún', 'foods': [
            {'foodName': 'Atún en agua', 'quantity': 100, 'unit': 'g', 'calories': 100, 'protein': 22, 'carbohydrates': 0, 'fat': 1}]},
    ],
    'recommendations': ['Mantente hidratada durante el día.'],
})


class FakeLLMClient:
    provider_name = 'fake'
    model = 'fake-model'

    def __init__(self, plan=None, error=None):
        self.plan = plan
        self.error = error
        self.calls = 0

    async def generate_structured(self, *, system_prompt, user_prompt, response_model, temperature=0.2):
        self.calls += 1
        if self.error:
            raise self.error
        return self.plan, 'raw-output-de-prueba'


class GenerateDraftTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'generate.db'
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

    async def calculated_consultation(self, **changes):
        consultation = await self.consultation(**changes)
        response = await self.client.post(f"consultations/{consultation['id']}/calculate")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def test_consulta_inexistente_devuelve_404(self):
        response = await self.client.post(f'consultations/{uuid4()}/generate-draft')
        self.assertEqual(response.status_code, 404)

    async def test_consulta_incompleta_devuelve_422(self):
        patient = await self.patient()
        response = await self.client.post(f"patients/{patient['id']}/consultations", json={})
        self.assertEqual(response.status_code, 201, response.text)
        incomplete = response.json()
        result = await self.client.post(f"consultations/{incomplete['id']}/generate-draft")
        self.assertEqual(result.status_code, 422)

    async def test_calculo_faltante_devuelve_409(self):
        consultation = await self.consultation()  # completa, pero sin /calculate
        response = await self.client.post(f"consultations/{consultation['id']}/generate-draft")
        self.assertEqual(response.status_code, 409)
        self.assertIn('calcularse', response.json()['message'])

    async def test_json_valido_crea_diet_plan_draft(self):
        consultation = await self.calculated_consultation()
        # Aislado del BAM.xlsx y del Qdrant reales que puedan existir en este entorno
        # (sección 33 de Fase 5: no se debe depender del estado ambiental, cada prueba
        # controla su fixture) — incluida la etapa de integración de recursos reales,
        # que puebla la colección Qdrant compartida con documentos auténticos.
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(Path(tmp) / 'BAM.xlsx')}), \
                    patch.object(rag_engine.knowledge_base_service, 'search', return_value=[]):
                food_db.reset_food_database_cache()
                result = await diet_plan_generation.generate_draft(
                    self.db, consultation['id'], llm_client=FakeLLMClient(plan=VALID_PLAN))
        food_db.reset_food_database_cache()

        self.assertEqual(result.status, 'SUCCESS')
        self.assertEqual(result.plan.status, 'DRAFT')
        self.assertEqual(result.plan.version, 1)
        self.assertEqual(len(result.plan.meals), 5)
        self.assertFalse(result.foodDatabaseUsed)
        self.assertFalse(result.knowledgeBaseUsed)

        self.assertEqual(await self.db.dietplan.count(), 1)
        self.assertEqual(await self.db.dietplanmeal.count(), 5)
        self.assertEqual(await self.db.dietplanfood.count(), 5)
        self.assertEqual(await self.db.plannutrientobservation.count(), 4)

        generation = await self.db.aigeneration.find_unique(where={'id': result.generationId})
        self.assertEqual(generation.status, 'SUCCESS')
        self.assertEqual(generation.promptVersion, diet_plan_generation.DIET_PLAN_PROMPT_VERSION)
        # Fase 6: la generación registra explícitamente si usó BAM/RAG (trazabilidad).
        self.assertFalse(generation.foodDatabaseUsed)
        self.assertFalse(generation.knowledgeBaseUsed)

        plan_row = await self.db.dietplan.find_unique(where={'id': result.dietPlanId})
        self.assertEqual(plan_row.summary, 'Borrador de prueba')
        self.assertEqual(json.loads(plan_row.recommendations), ['Mantente hidratada durante el día.'])

        codes = {v.code for v in await self.db.planvalidation.find_many(where={'dietPlanId': result.dietPlanId})}
        self.assertIn('FOOD_DATABASE_UNAVAILABLE', codes)
        self.assertIn('KNOWLEDGE_BASE_UNAVAILABLE', codes)

        link = await self.db.generationplanlink.find_unique(where={'generationId': result.generationId})
        self.assertEqual(link.dietPlanId, result.dietPlanId)
        self.assertTrue(link.isOrigin)

        # Nunca se afirma "SMAE validado": sin fuente estructurada, el equivalente siempre es null.
        foods = await self.db.dietplanfood.find_many()
        self.assertTrue(all(food.smaeEquivalent is None for food in foods))

    async def test_bam_tiene_precedencia_sobre_el_llm_en_coincidencia_confiable(self):
        """Sección 24: coincidencia exacta con BAM (gramos) reemplaza kcal/macros del
        LLM; alimentos sin coincidencia quedan con el valor del LLM y una validación
        FOOD_NUTRIENTS_PARTIALLY_VERIFIED (nunca se confían en silencio)."""
        consultation = await self.calculated_consultation()
        with tempfile.TemporaryDirectory() as tmp:
            bam_path = Path(tmp) / 'BAM.xlsx'
            # Solo "Avena" (40 g en VALID_PLAN) tiene coincidencia exacta real.
            _write_bam(bam_path, rows=[['9001', 'AVENA', 389, 16.9, 6.9, 66.3]])
            with patch.dict('os.environ', {'ALIMENTIA_FOOD_DB_PATH': str(bam_path)}):
                food_db.reset_food_database_cache()
                result = await diet_plan_generation.generate_draft(
                    self.db, consultation['id'], llm_client=FakeLLMClient(plan=VALID_PLAN))
        food_db.reset_food_database_cache()

        self.assertTrue(result.foodDatabaseUsed)
        foods = await self.db.dietplanfood.find_many(where={'foodName': 'Avena'})
        self.assertEqual(len(foods), 1)
        avena = foods[0]
        self.assertAlmostEqual(avena.calories, 389 * 0.4, places=2)
        self.assertAlmostEqual(avena.protein, 16.9 * 0.4, places=2)
        self.assertAlmostEqual(avena.carbohydrates, 66.3 * 0.4, places=2)
        self.assertAlmostEqual(avena.fat, 6.9 * 0.4, places=2)

        # El resto (Manzana, Pechuga de pollo, Yogur natural, Atún en agua) no tiene
        # coincidencia exacta en este BAM sintético: conservan el valor del LLM.
        manzana = await self.db.dietplanfood.find_first(where={'foodName': 'Manzana'})
        self.assertEqual(manzana.calories, 95)

        codes = {v.code for v in await self.db.planvalidation.find_many(where={'dietPlanId': result.dietPlanId})}
        self.assertIn('FOOD_NUTRIENTS_PARTIALLY_VERIFIED', codes)
        self.assertNotIn('FOOD_DATABASE_UNAVAILABLE', codes)

    async def test_json_invalido_no_crea_plan_y_registra_generacion_fallida(self):
        consultation = await self.calculated_consultation()
        fake_client = FakeLLMClient(error=LLMGenerationError('JSON inválido de prueba'))

        with self.assertRaises(CaptureError) as ctx:
            await diet_plan_generation.generate_draft(self.db, consultation['id'], llm_client=fake_client)
        self.assertEqual(ctx.exception.status, 502)

        self.assertEqual(await self.db.dietplan.count(), 0)
        generations = await self.db.aigeneration.find_many()
        self.assertEqual(len(generations), 1)
        self.assertEqual(generations[0].status, 'FAILED')
        self.assertIn('JSON inválido de prueba', generations[0].errorMessage)

    async def test_recalculo_no_sobrescribe_historial(self):
        consultation = await self.calculated_consultation()
        first = await diet_plan_generation.generate_draft(
            self.db, consultation['id'], llm_client=FakeLLMClient(plan=VALID_PLAN))
        second = await diet_plan_generation.generate_draft(
            self.db, consultation['id'], llm_client=FakeLLMClient(plan=VALID_PLAN))

        self.assertEqual(first.version, 1)
        self.assertEqual(second.version, 2)
        self.assertNotEqual(first.dietPlanId, second.dietPlanId)
        self.assertEqual(await self.db.dietplan.count(), 2)

    async def test_sourceid_slug_resuelve_a_uuid_y_persiste_retrieved_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp)
            (knowledge_dir / 'guia.pdf').write_text('contenido de prueba')
            manifest_path = knowledge_dir / 'manifest.json'
            manifest_path.write_text(json.dumps({'version': '1.0', 'sources': [
                {'id': 'insp-guia-2015', 'name': 'Guía INSP', 'institution': 'INSP', 'file': 'guia.pdf'},
            ]}), encoding='utf-8')
            with patch.dict('os.environ', {'ALIMENTIA_KNOWLEDGE_MANIFEST_PATH': str(manifest_path)}):
                await sync_knowledge_sources(self.db, knowledge_dir)
                chunk = types.SimpleNamespace(sourceId='insp-guia-2015', documentName='Guía INSP',
                    institution='INSP', version=None, section='Fibra', content='Recomendación de fibra.', score=0.9)
                with patch.object(rag_engine.knowledge_base_service, 'search', return_value=[chunk]):
                    consultation = await self.calculated_consultation()
                    result = await diet_plan_generation.generate_draft(
                        self.db, consultation['id'], llm_client=FakeLLMClient(plan=VALID_PLAN))

        self.assertTrue(result.knowledgeBaseUsed)
        self.assertEqual(len(result.sources), 1)
        source_row = await self.db.knowledgesource.find_first(where={'originalFilename': 'guia.pdf'})
        self.assertEqual(result.sources[0].knowledgeSourceId, source_row.id)
        retrieved = await self.db.retrievedsource.find_many(where={'generationId': result.generationId})
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0].knowledgeSourceId, source_row.id)

    async def test_fuente_inexistente_no_persistida(self):
        chunk = types.SimpleNamespace(sourceId='no-declarada-en-manifiesto', documentName='Fantasma',
            institution=None, version=None, section=None, content='contenido fantasma', score=0.5)
        with patch.object(rag_engine.knowledge_base_service, 'search', return_value=[chunk]):
            consultation = await self.calculated_consultation()
            result = await diet_plan_generation.generate_draft(
                self.db, consultation['id'], llm_client=FakeLLMClient(plan=VALID_PLAN))

        self.assertEqual(result.sources, [])
        self.assertEqual(await self.db.retrievedsource.count(), 0)

    async def test_calculo_no_crea_paciente_ni_consulta_nueva(self):
        consultation = await self.calculated_consultation()
        self.assertEqual(await self.db.patient.count(), 1)
        self.assertEqual(await self.db.nutritionconsultation.count(), 1)
        await diet_plan_generation.generate_draft(self.db, consultation['id'], llm_client=FakeLLMClient(plan=VALID_PLAN))
        self.assertEqual(await self.db.patient.count(), 1)
        self.assertEqual(await self.db.nutritionconsultation.count(), 1)


if __name__ == '__main__':
    unittest.main()
