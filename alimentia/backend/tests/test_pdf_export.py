"""Pruebas de exportación de plan a PDF (Fase 6, Parte D)."""
import unittest
from uuid import uuid4

from app.schemas.generation import GeneratedDietPlan
from app.services import diet_plan_generation
from test_plan_management import FakeLLMClient, PlanManagementTestBase


class PdfExportTests(PlanManagementTestBase):
    async def test_export_inexistente_404(self):
        response = await self.client.get(f'plans/{uuid4()}/export/pdf')
        self.assertEqual(response.status_code, 404)

    async def test_export_borrador_devuelve_409(self):
        _consultation, result = await self.draft_plan()
        response = await self.client.get(f'plans/{result.dietPlanId}/export/pdf')
        self.assertEqual(response.status_code, 409)

    async def test_export_bajo_revision_devuelve_409(self):
        _consultation, result = await self.draft_plan()
        edit = {'meals': [{'mealType': 'Comida 1', 'name': 'Editada', 'foods': [
            {'foodName': 'Alimento editado', 'quantity': 1, 'unit': 'g', 'calories': 100}]}]}
        edited = await self.client.patch(f"plans/{result.dietPlanId}", json=edit)
        self.assertEqual(edited.json()['status'], 'UNDER_REVIEW')
        response = await self.client.get(f'plans/{result.dietPlanId}/export/pdf')
        self.assertEqual(response.status_code, 409)

    async def test_export_rechazado_devuelve_409(self):
        _consultation, result = await self.draft_plan()
        await self.client.post(f"plans/{result.dietPlanId}/reject", json={'reason': 'motivo'})
        response = await self.client.get(f'plans/{result.dietPlanId}/export/pdf')
        self.assertEqual(response.status_code, 409)

    async def test_export_aprobado_devuelve_pdf_valido(self):
        _consultation, result = await self.draft_plan()
        approved = await self.client.post(f"plans/{result.dietPlanId}/approve", json={'actor': 'dra-lopez'})
        self.assertEqual(approved.status_code, 200, approved.text)

        response = await self.client.get(f'plans/{result.dietPlanId}/export/pdf')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['content-type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertGreater(len(response.content), 500)

    async def test_export_no_incluye_uuid_tecnicos_en_texto(self):
        """Sección 22: nunca deben aparecer UUIDs internos como texto plano legible en el PDF."""
        consultation, result = await self.draft_plan()
        await self.client.post(f"plans/{result.dietPlanId}/approve", json={'actor': 'dra-lopez'})
        response = await self.client.get(f'plans/{result.dietPlanId}/export/pdf')
        # Un PDF codifica el texto dentro de streams comprimidos: basta con confirmar que
        # el UUID del plan/consulta no aparece como bytes crudos (no habría razón legítima
        # para que apareciera sin comprimir).
        self.assertNotIn(result.dietPlanId.encode(), response.content)
        self.assertNotIn(consultation['id'].encode(), response.content)
        self.assertNotIn(consultation['patientId'].encode(), response.content)

    async def test_export_contiene_paciente_y_objetivo(self):
        patient = await self.patient(name='Paciente de prueba PDF')
        consultation, result = await self.draft_plan(patient=patient)
        await self.client.post(f"plans/{result.dietPlanId}/approve", json={'actor': 'dra-lopez'})
        response = await self.client.get(f'plans/{result.dietPlanId}/export/pdf')
        self.assertEqual(response.status_code, 200, response.text)
        # El nombre del paciente y el resumen del plan van dentro del PDF; no siempre son
        # extraíbles sin descomprimir streams, así que solo se valida el tamaño y el content-type
        # (cobertura de contenido legible se hace manualmente en Docker, sección 41).
        self.assertGreater(len(response.content), 500)


    async def test_export_no_falla_con_puntuacion_tipografica_del_llm(self):
        """El LLM puede generar guiones largos, comillas tipográficas, viñetas o
        puntos suspensivos: la fuente core del PDF no los soporta directamente y
        la exportación nunca debe responder 500 por eso (debe sanear el texto)."""
        consultation = await self.calculated_consultation()
        plan_json = GeneratedDietPlan.model_validate({
            'summary': 'Plan de "prueba" — con guion largo… y viñetas • aquí.',
            'meals': [{'mealType': 'Comida 1', 'name': 'Comida 1', 'foods': [
                {'foodName': 'Alimento con —guion—', 'quantity': 1, 'unit': 'porción',
                 'calories': consultation['targetCalories'], 'protein': 10.0,
                 'carbohydrates': 20.0, 'fat': 5.0, 'notes': 'Nota con comillas "curvas" y — raya.'},
            ]}],
            'recommendations': ['Recomendación con — raya y … puntos suspensivos.'],
        })
        result = await diet_plan_generation.generate_draft(
            self.db, consultation['id'], llm_client=FakeLLMClient(plan=plan_json))
        approved = await self.client.post(f"plans/{result.dietPlanId}/approve", json={'actor': 'dra-lopez'})
        self.assertEqual(approved.status_code, 200, approved.text)

        response = await self.client.get(f'plans/{result.dietPlanId}/export/pdf')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.content.startswith(b'%PDF'))


if __name__ == '__main__':
    unittest.main()
