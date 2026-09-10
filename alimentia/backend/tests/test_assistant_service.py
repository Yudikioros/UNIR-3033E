"""
Pruebas del asistente híbrido (corrección post-lanzamiento):

- `RouterFastPathTests`: preguntas conocidas se responden sin invocar al LLM
  ni una sola vez (`llm.prompts` debe quedar vacío) -esto es lo que corrige
  el problema real de ~180s por pregunta y de selección incorrecta de
  herramientas-.
- `GeneralAssistantLoopTests`: el bucle LLM->tool->LLM original se conserva
  íntegro, pero ahora solo se alcanza para preguntas que el router no
  reconoce (`GENERAL_ASSISTANT`).
- `SmartFallbackTests`: un id con forma de nombre nunca llega a `get_patient`
  real, ni siquiera dentro del bucle de fallback -el caso exacto reportado
  en producción (`get_patient("María González")`)-.
- `GroundingGuardrailTests`: el asistente nunca contradice el estado
  estructurado real, ahora demostrado también en el camino 100%
  determinístico (cero llamadas LLM) además del camino con LLM.
"""
import unittest
from unittest.mock import patch

from app.schemas.assistant import AssistantChatRequest, AssistantDecision, AssistantExplanation, AssistantNavigationContext
from app.services import assistant_service, rag_engine
from app.services.assistant_service import AlimentiaAssistantService, MAX_TOOL_ITERATIONS
from app.services.llm_client import LLMGenerationError
from test_plan_management import PlanManagementTestBase


class ScriptedAssistantLLM:
    provider_name = "fake"
    model = "fake-model"

    def __init__(self, decisions=None, error=None):
        self.decisions = list(decisions or [])
        self.error = error
        self.prompts: list[str] = []

    async def generate_structured(self, *, system_prompt, user_prompt, response_model, temperature=0.2):
        self.prompts.append(user_prompt)
        if self.error:
            raise self.error
        if not self.decisions:
            raise AssertionError("ScriptedAssistantLLM se quedó sin decisiones guionadas.")
        decision = self.decisions.pop(0)
        return decision, decision.model_dump_json()


def _request(message="", **context) -> AssistantChatRequest:
    return AssistantChatRequest(message=message or "pregunta de prueba",
        context=AssistantNavigationContext(**context))


class RouterFastPathTests(PlanManagementTestBase):
    """Sección 21: cada uno de estos casos debe resolverse SIN llamar al LLM."""

    async def test_pregunta_por_nombre_no_usa_llm(self):
        await self.patient(name="Ana Torres")
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("¿Quién es Ana Torres?"))
        self.assertEqual(llm.prompts, [])
        self.assertEqual(response.toolsUsed, ["search_patients", "get_patient"])
        self.assertIn("Ana Torres", response.answer)
        self.assertEqual(response.metadata.responseMode, "deterministic")
        self.assertEqual(response.metadata.llmExecutionTimeMs, 0)

    async def test_paciente_no_encontrado_no_usa_llm(self):
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("¿Quién es Roberto Nadie?"))
        self.assertEqual(llm.prompts, [])
        self.assertIn("No encontré", response.answer)

    async def test_multiples_coincidencias_no_usa_llm(self):
        await self.patient(name="María González")
        await self.patient(name="María Pérez")
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("¿Qué planes tiene María?"))
        self.assertEqual(llm.prompts, [])
        self.assertIn("más de un paciente", response.answer)

    async def test_planes_de_un_paciente_por_nombre(self):
        """Caso real reportado: 'María González' nunca debe pasarse como id."""
        patient = await self.patient(name="María González")
        await self.draft_plan(patient=patient)
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("¿Qué planes tiene María González?"))
        self.assertEqual(llm.prompts, [])
        self.assertEqual(response.toolsUsed, ["search_patients", "get_patient", "get_patient_plans"])
        self.assertIn(patient["name"], response.answer)
        self.assertIn("Versión 1", response.answer)

    async def test_consultas_de_un_paciente(self):
        patient = await self.patient(name="Carlos Ruiz")
        await self.consultation(patient=patient)
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("¿Qué consultas tiene Carlos Ruiz?"))
        self.assertEqual(llm.prompts, [])
        self.assertIn("1 consulta", response.answer)

    async def test_calculo_nutricional_de_un_paciente(self):
        patient = await self.patient(name="Laura Méndez")
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("¿Cuántas calorías necesita Laura Méndez?"))
        self.assertEqual(llm.prompts, [])
        self.assertIn(patient["name"], response.answer)
        self.assertIn("todavía no tiene ninguna consulta", response.answer)

    async def test_plan_detail_usa_contexto_de_navegacion_sin_llm(self):
        _consultation, result = await self.draft_plan()
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db,
            _request("¿Cuántas calorías tiene este plan?", planId=result.dietPlanId))
        self.assertEqual(llm.prompts, [])
        self.assertEqual(response.toolsUsed, ["get_plan"])
        self.assertEqual(response.metadata.responseMode, "deterministic")

    async def test_plan_approval_status_sin_llm(self):
        _consultation, result = await self.draft_plan()
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db,
            _request("¿se puede aprobar este plan?", planId=result.dietPlanId))
        self.assertEqual(llm.prompts, [])
        self.assertIn("puede aprobarse", response.answer)

    async def test_plan_validations_sin_llm(self):
        _consultation, result = await self.draft_plan(target_calories=1000000)
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db,
            _request("¿qué validaciones tiene el plan actual?", planId=result.dietPlanId))
        self.assertEqual(llm.prompts, [])
        self.assertIn("Bloqueantes", response.answer)

    async def test_conteo_de_planes_por_estado_sin_llm(self):
        await self.draft_plan()
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("¿cuántos planes están en borrador?"))
        self.assertEqual(llm.prompts, [])
        self.assertIn("borrador", response.answer.lower())

    async def test_pacientes_por_estado_de_plan_sin_llm(self):
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("¿qué pacientes tienen planes aprobados?"))
        self.assertEqual(llm.prompts, [])
        self.assertIn("No hay ningún paciente", response.answer)

    async def test_listar_fuentes_documentales_sin_llm(self):
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("¿qué fuentes documentales están disponibles?"))
        self.assertEqual(llm.prompts, [])
        self.assertIn("No hay fuentes documentales", response.answer)

    async def test_busqueda_documental_sin_resultados_no_usa_llm(self):
        llm = ScriptedAssistantLLM()
        with patch.object(rag_engine.knowledge_base_service, "search", return_value=[]):
            service = AlimentiaAssistantService(llm_client=llm)
            response = await service.chat(self.db, _request("¿qué dicen las fuentes sobre fibra?"))
        self.assertEqual(llm.prompts, [])
        self.assertEqual(response.answer, assistant_service.NO_SOURCES_MESSAGE)

    async def test_busqueda_documental_con_resultados_usa_una_sola_llamada_llm(self):
        """Sección 7: para RAG con resultados sí se permite 1 llamada LLM de
        síntesis -nunca cero, nunca más de una-."""
        class _Chunk:
            sourceId, documentName, institution, version, content = "s1", "Guía Nacional", "SSA", "1", "La fibra ayuda a..."

        llm = ScriptedAssistantLLM(decisions=[
            AssistantExplanation(answer="Según la Guía Nacional, la fibra ayuda a la digestión."),
        ])
        with patch.object(rag_engine.knowledge_base_service, "search", return_value=[_Chunk()]):
            service = AlimentiaAssistantService(llm_client=llm)
            response = await service.chat(self.db, _request("¿qué dicen las fuentes sobre fibra?"))
        self.assertEqual(len(llm.prompts), 1)
        self.assertIn("Guía Nacional", response.answer)
        self.assertEqual(response.metadata.responseMode, "llm")
        self.assertEqual(len(response.sources), 1)


class ExplanationOptOutTests(PlanManagementTestBase):
    async def test_explicacion_opcional_agrega_una_sola_llamada_llm(self):
        _consultation, result = await self.draft_plan()
        llm = ScriptedAssistantLLM(decisions=[AssistantExplanation(answer="En resumen, este plan está en revisión.")])
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db,
            _request("Explícame este plan, por favor", planId=result.dietPlanId))
        self.assertEqual(len(llm.prompts), 1)
        self.assertIn("En resumen", response.answer)
        self.assertEqual(response.metadata.responseMode, "llm")

    async def test_explicacion_sin_peticion_no_usa_llm(self):
        _consultation, result = await self.draft_plan()
        llm = ScriptedAssistantLLM()
        service = AlimentiaAssistantService(llm_client=llm)
        await service.chat(self.db, _request("¿cuántas calorías tiene este plan?", planId=result.dietPlanId))
        self.assertEqual(llm.prompts, [])

    async def test_fallo_del_llm_en_explicacion_no_rompe_la_respuesta(self):
        """Sección 39: el hecho determinístico ya es una respuesta válida por
        sí solo; si el LLM de explicación falla, se devuelve igual."""
        _consultation, result = await self.draft_plan()
        llm = ScriptedAssistantLLM(error=LLMGenerationError("Ollama no responde"))
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db,
            _request("Explícame este plan", planId=result.dietPlanId))
        self.assertTrue(response.answer)
        self.assertNotEqual(response.answer, assistant_service.UNAVAILABLE_MESSAGE)


class ComparisonIntentTests(PlanManagementTestBase):
    async def test_comparacion_de_dos_planes_usa_exactamente_una_llamada_llm(self):
        """Sección 7: la comparación de versiones siempre se narra -a
        diferencia de las demás intenciones deterministas, aquí SÍ se llama
        al LLM exactamente una vez, nunca cero ni dos-."""
        _c1, r1 = await self.draft_plan()
        _c2, r2 = await self.draft_plan()
        llm = ScriptedAssistantLLM(decisions=[
            AssistantExplanation(answer="Ambas versiones tienen una energía similar."),
        ])
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db,
            _request(f"¿Cuál es la diferencia entre el plan {r1.dietPlanId} y el plan {r2.dietPlanId}?"))
        self.assertEqual(response.toolsUsed, ["compare_plan_versions"])
        self.assertEqual(len(llm.prompts), 1)
        self.assertIn("Ambas versiones", response.answer)
        self.assertIn("Comparación", response.answer)


class SmartFallbackTests(PlanManagementTestBase):
    """Sección 9/10: aunque el router no reconozca la pregunta y se llegue al
    bucle con LLM, un id con forma de nombre nunca se ejecuta como
    `get_patient` real -se redirige a `search_patients` automáticamente-."""

    async def test_get_patient_con_nombre_se_redirige_a_search_patients(self):
        await self.patient(name="María González")
        llm = ScriptedAssistantLLM(decisions=[
            AssistantDecision(action="use_tool", tool="get_patient", arguments={"patient_id": "María González"}),
            AssistantDecision(action="answer", answer="María González es una paciente registrada."),
        ])
        service = AlimentiaAssistantService(llm_client=llm)
        # Mensaje deliberadamente ambiguo para forzar GENERAL_ASSISTANT y ejercer el bucle con LLM.
        response = await service.chat(self.db, _request("dame información sobre ella, por favor"))
        self.assertEqual(response.toolsUsed, ["search_patients"])
        self.assertIn("María González", response.answer)

    async def test_get_patient_con_id_malformado_sin_coincidencias(self):
        llm = ScriptedAssistantLLM(decisions=[
            AssistantDecision(action="use_tool", tool="get_patient", arguments={"patient_id": "Nombre Inventado"}),
            AssistantDecision(action="answer", answer="No encontré a esa persona."),
        ])
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("dame información sobre ella, por favor"))
        self.assertEqual(response.toolsUsed, ["search_patients"])
        self.assertIn("No se encontró", llm.prompts[-1])


class GeneralAssistantLoopTests(PlanManagementTestBase):
    """El bucle LLM->tool->LLM original, ahora solo alcanzable vía GENERAL_ASSISTANT."""

    async def test_respuesta_directa_sin_herramientas(self):
        llm = ScriptedAssistantLLM(decisions=[
            AssistantDecision(action="answer", answer="Hola, soy el asistente de AlimentIA."),
        ])
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("hola"))
        self.assertEqual(response.answer, "Hola, soy el asistente de AlimentIA.")
        self.assertEqual(response.toolsUsed, [])
        self.assertEqual(response.metadata.model, "fake-model")
        self.assertEqual(response.metadata.responseMode, "llm")

    async def test_decision_use_tool_sin_herramienta_no_rompe_el_flujo(self):
        malformed = AssistantDecision.model_construct(action="use_tool", tool=None, arguments={}, answer=None)
        llm = ScriptedAssistantLLM(decisions=[malformed])
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("bórrame todos los pacientes"))
        self.assertEqual(response.answer, assistant_service.NO_ANSWER_MESSAGE)

    async def test_tool_error_por_paciente_inexistente_continua_el_bucle(self):
        missing_id = "00000000-0000-4000-8000-000000000000"
        llm = ScriptedAssistantLLM(decisions=[
            AssistantDecision(action="use_tool", tool="get_patient", arguments={"patient_id": missing_id}),
            AssistantDecision(action="answer", answer="No encontré a ese paciente en AlimentIA."),
        ])
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("dime sobre el paciente con ese identificador"))
        self.assertIn("No encontré", response.answer)
        self.assertEqual(response.toolsUsed, ["get_patient"])

    async def test_limite_de_iteraciones_no_hace_loop_infinito(self):
        patient = await self.patient()
        decisions = [
            AssistantDecision(action="use_tool", tool="get_patient", arguments={"patient_id": patient["id"], "attempt": str(i)})
            for i in range(MAX_TOOL_ITERATIONS + 2)
        ]
        llm = ScriptedAssistantLLM(decisions=decisions)
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("pregunta ambigua"))
        self.assertEqual(len(response.toolsUsed), MAX_TOOL_ITERATIONS)
        self.assertTrue(response.answer)

    async def test_no_repite_la_misma_llamada(self):
        patient = await self.patient()
        llm = ScriptedAssistantLLM(decisions=[
            AssistantDecision(action="use_tool", tool="get_patient", arguments={"patient_id": patient["id"]}),
            AssistantDecision(action="use_tool", tool="get_patient", arguments={"patient_id": patient["id"]}),
            AssistantDecision(action="answer", answer="Listo."),
        ])
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("repite la consulta"))
        self.assertEqual(response.toolsUsed, ["get_patient"])
        self.assertIn("Ya se ejecutó", llm.prompts[-1])

    async def test_proveedor_no_disponible(self):
        llm = ScriptedAssistantLLM(error=LLMGenerationError("Ollama no responde"))
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("hola"))
        self.assertEqual(response.answer, "No fue posible consultar al asistente en este momento.")

    async def test_contexto_de_navegacion_llega_al_prompt(self):
        patient = await self.patient()
        llm = ScriptedAssistantLLM(decisions=[AssistantDecision(action="answer", answer="ok")])
        service = AlimentiaAssistantService(llm_client=llm)
        await service.chat(self.db, _request("hola", route="/patients/x", patientId=patient["id"]))
        self.assertIn(patient["id"], llm.prompts[0])
        self.assertIn("/patients/x", llm.prompts[0])

    async def test_no_envia_pii_innecesaria_al_llm(self):
        patient = await self.patient(name="Carlos Ruiz López", email="carlos@example.com", phone="555-0100")
        llm = ScriptedAssistantLLM(decisions=[
            AssistantDecision(action="use_tool", tool="get_patient", arguments={"patient_id": patient["id"]}),
            AssistantDecision(action="answer", answer="Carlos Ruiz López está registrado."),
        ])
        service = AlimentiaAssistantService(llm_client=llm)
        await service.chat(self.db, _request("dame el registro completo con ese identificador"))
        combined_prompts = " ".join(llm.prompts)
        self.assertNotIn("carlos@example.com", combined_prompts)
        self.assertNotIn("555-0100", combined_prompts)


class GroundingGuardrailTests(PlanManagementTestBase):
    async def test_caso1_preserva_target_calories_real(self):
        """La DB dice targetCalories = X; el LLM intenta responder Y; la
        respuesta final debe conservar X (nunca lo que "dijo" el LLM)."""
        consultation = await self.calculated_consultation()
        real_target = consultation["targetCalories"]
        llm = ScriptedAssistantLLM(decisions=[
            AssistantDecision(action="use_tool", tool="get_consultation_calculation",
                arguments={"consultation_id": consultation["id"]}),
            AssistantDecision(action="answer", answer="El objetivo energético es de 9999 kcal."),
        ])
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("¿cuál es el objetivo energético de esta persona?",
            consultationId=consultation["id"]))
        self.assertIn(f"{real_target:.0f} kcal", response.answer)
        self.assertEqual(response.structuredData["targetCalories"], real_target)

    async def test_caso2_sin_fuentes_no_expone_cita_inventada(self):
        """Sin documentos autorizados, el modelo no debe poder "citar" una
        fuente: la respuesta final se decide de forma determinística, sin
        siquiera invocar al LLM."""
        llm = ScriptedAssistantLLM(decisions=[
            AssistantDecision(action="use_tool", tool="search_knowledge", arguments={"query": "fibra"}),
            AssistantDecision(action="answer", answer="Según la Guía Nacional de Nutrición, se recomienda..."),
        ])
        with patch.object(rag_engine.knowledge_base_service, "search", return_value=[]):
            service = AlimentiaAssistantService(llm_client=llm)
            response = await service.chat(self.db, _request("¿qué dicen las fuentes sobre fibra?"))
        self.assertEqual(response.answer, "No hay fuentes documentales configuradas actualmente para responder esta pregunta.")
        self.assertEqual(response.sources, [])
        self.assertNotIn("Guía Nacional", response.answer)
        self.assertEqual(llm.prompts, [])

    async def test_caso3_no_contradice_validacion_bloqueante(self):
        """El plan tiene una validación bloqueante; se pregunta si puede
        aprobarse con el plan abierto en el contexto de navegación; la
        respuesta -100% determinística, cero llamadas LLM- no puede
        contradecir el estado estructurado real."""
        _consultation, result = await self.draft_plan(target_calories=1000000)
        llm = ScriptedAssistantLLM(decisions=[
            AssistantDecision(action="use_tool", tool="get_plan", arguments={"plan_id": result.dietPlanId}),
            AssistantDecision(action="answer", answer="Este plan puede aprobarse sin problema."),
        ])
        service = AlimentiaAssistantService(llm_client=llm)
        response = await service.chat(self.db, _request("¿se puede aprobar este plan?", planId=result.dietPlanId))
        self.assertFalse(response.structuredData["canApprove"])
        self.assertIn("no puede aprobarse todavía", response.answer)
        self.assertEqual(llm.prompts, [])
        self.assertEqual(response.metadata.responseMode, "deterministic")


if __name__ == "__main__":
    unittest.main()
