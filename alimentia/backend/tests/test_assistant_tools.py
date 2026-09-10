"""Pruebas de las herramientas READ-ONLY del asistente IA (sección 8/40)."""
import unittest
from unittest.mock import patch

from app.services import assistant_tools, rag_engine
from app.services.assistant_tools import ToolError
from test_plan_management import PlanManagementTestBase


class PatientToolsTests(PlanManagementTestBase):
    async def test_get_patient_encontrado(self):
        patient = await self.patient(name="Ana Torres")
        result = await assistant_tools.get_patient_tool(self.db, patient["id"])
        self.assertEqual(result.name, "Ana Torres")
        self.assertFalse(hasattr(result, "email"))
        self.assertFalse(hasattr(result, "phone"))

    async def test_get_patient_inexistente(self):
        with self.assertRaises(ToolError):
            await assistant_tools.get_patient_tool(self.db, "no-existe")

    async def test_get_patient_parametro_vacio(self):
        with self.assertRaises(ToolError):
            await assistant_tools.get_patient_tool(self.db, "  ")

    async def test_search_patients_una_coincidencia(self):
        await self.patient(name="Beatriz Núñez")
        results = await assistant_tools.search_patients_tool(self.db, "Beatriz")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Beatriz Núñez")

    async def test_search_patients_multiples_coincidencias(self):
        await self.patient(name="María González")
        await self.patient(name="María Pérez")
        results = await assistant_tools.search_patients_tool(self.db, "María")
        self.assertEqual(len(results), 2)

    async def test_search_patients_sin_coincidencias(self):
        results = await assistant_tools.search_patients_tool(self.db, "Nadie Existe")
        self.assertEqual(results, [])

    async def test_search_patients_query_vacio_no_lista_todo(self):
        await self.patient(name="Carlos Ruiz")
        with self.assertRaises(ToolError):
            await assistant_tools.search_patients_tool(self.db, "")


class ConsultationToolsTests(PlanManagementTestBase):
    async def test_get_patient_consultations(self):
        consultation = await self.consultation()
        results = await assistant_tools.get_patient_consultations_tool(self.db, consultation["patientId"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, consultation["id"])

    async def test_get_consultation_encontrada(self):
        consultation = await self.consultation()
        result = await assistant_tools.get_consultation_tool(self.db, consultation["id"])
        self.assertEqual(result.id, consultation["id"])

    async def test_get_consultation_inexistente(self):
        with self.assertRaises(ToolError):
            await assistant_tools.get_consultation_tool(self.db, "no-existe")

    async def test_get_consultation_calculation_sin_calculo(self):
        consultation = await self.consultation()
        with self.assertRaises(ToolError):
            await assistant_tools.get_consultation_calculation_tool(self.db, consultation["id"])

    async def test_get_consultation_calculation_con_calculo(self):
        consultation = await self.calculated_consultation()
        result = await assistant_tools.get_consultation_calculation_tool(self.db, consultation["id"])
        self.assertEqual(result.calculationMethod, "MIFFLIN_ST_JEOR")
        self.assertEqual(result.calculationRuleVersion, "1.0")
        self.assertEqual(result.targetCalories, consultation["targetCalories"])
        self.assertIsNotNone(result.activityFactor)
        self.assertIsNotNone(result.macroDistributionPercentage)


class PlanToolsTests(PlanManagementTestBase):
    async def test_get_patient_plans(self):
        consultation, result = await self.draft_plan()
        plans = await assistant_tools.get_patient_plans_tool(self.db, consultation["patientId"])
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].id, result.dietPlanId)

    async def test_get_consultation_plans(self):
        consultation, result = await self.draft_plan()
        plans = await assistant_tools.get_consultation_plans_tool(self.db, consultation["id"])
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].version, 1)

    async def test_get_plan_encontrado(self):
        _consultation, result = await self.draft_plan()
        plan = await assistant_tools.get_plan_tool(self.db, result.dietPlanId)
        self.assertEqual(plan.id, result.dietPlanId)
        self.assertEqual(plan.status, "DRAFT")
        self.assertTrue(len(plan.meals) >= 1)

    async def test_get_plan_inexistente(self):
        with self.assertRaises(ToolError):
            await assistant_tools.get_plan_tool(self.db, "no-existe")

    async def test_get_plan_validations(self):
        consultation, result = await self.draft_plan(target_calories=1000000)  # fuerza desviación bloqueante
        validations = await assistant_tools.get_plan_validations_tool(self.db, result.dietPlanId)
        self.assertTrue(any(v.isBlocking for v in validations))

    async def test_get_plan_sources_vacio_sin_rag(self):
        _consultation, result = await self.draft_plan()
        sources = await assistant_tools.get_plan_sources_tool(self.db, result.dietPlanId)
        self.assertEqual(sources, [])

    async def test_compare_plan_versions(self):
        from app.repositories import plan_management as pm
        from app.schemas.plan_management import RegenerateRequest
        from test_plan_management import FakeLLMClient, _plan_json

        _consultation, first = await self.draft_plan()
        second = await pm.regenerate_plan(self.db, first.dietPlanId, RegenerateRequest(),
            llm_client=FakeLLMClient(plan=_plan_json(meals_per_day=1, calories_each=500.0)))

        comparison = await assistant_tools.compare_plan_versions_tool(self.db, first.dietPlanId, second.dietPlanId)
        self.assertEqual(comparison.planA.version, 1)
        self.assertEqual(comparison.planB.version, 2)
        self.assertIsNotNone(comparison.totalCaloriesDelta)


class KnowledgeToolsTests(PlanManagementTestBase):
    async def test_search_knowledge_sin_resultados(self):
        with patch.object(rag_engine.knowledge_base_service, "search", return_value=[]):
            results = await assistant_tools.search_knowledge_tool(self.db, "fibra")
        self.assertEqual(results, [])

    async def test_search_knowledge_con_resultados(self):
        import types
        chunk = types.SimpleNamespace(sourceId="insp-2015", documentName="Guía INSP", institution="INSP",
            version="2015", content="Contenido de referencia sobre fibra." * 50)
        with patch.object(rag_engine.knowledge_base_service, "search", return_value=[chunk]):
            results = await assistant_tools.search_knowledge_tool(self.db, "fibra")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].sourceId, "insp-2015")
        self.assertLessEqual(len(results[0].content), 800)

    async def test_list_knowledge_sources_vacio(self):
        results = await assistant_tools.list_knowledge_sources_tool(self.db)
        self.assertEqual(results, [])


class AggregateToolsTests(PlanManagementTestBase):
    async def test_count_plans_by_status(self):
        await self.draft_plan()
        counts = await assistant_tools.count_plans_by_status_tool(self.db)
        self.assertTrue(any(item.status == "DRAFT" and item.count >= 1 for item in counts))

    async def test_list_patients_by_plan_status(self):
        consultation, result = await self.draft_plan()
        rows = await assistant_tools.list_patients_by_plan_status_tool(self.db, "draft")
        self.assertTrue(any(row.planId == result.dietPlanId for row in rows))

    async def test_list_patients_by_plan_status_sin_coincidencias(self):
        rows = await assistant_tools.list_patients_by_plan_status_tool(self.db, "APPROVED")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
