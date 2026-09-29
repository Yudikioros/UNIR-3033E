"""
Pruebas del router determinístico del asistente (corrección post-lanzamiento,
sección 21): `route()` nunca debe llamar al LLM -no hay red ni Ollama en este
archivo, es 100% lógica de cadenas- y debe clasificar correctamente las
preguntas frecuentes descritas en el pedido de corrección.
"""
import unittest

from app.schemas.assistant import AssistantNavigationContext
from app.services.assistant_router import Intent, is_valid_id, route


def _ctx(**kwargs) -> AssistantNavigationContext:
    return AssistantNavigationContext(**kwargs)


class IsValidIdTests(unittest.TestCase):
    def test_uuid_valido(self):
        self.assertTrue(is_valid_id("47c0bccf-420c-4685-9141-84f90f89ebb0"))

    def test_id_legado_con_prefijo(self):
        self.assertTrue(is_valid_id("legacy-consultation-47c0bccf-420c-4685-9141-84f90f89ebb0"))

    def test_nombre_no_es_id(self):
        self.assertFalse(is_valid_id("María González"))

    def test_vacio_no_es_id(self):
        self.assertFalse(is_valid_id(""))
        self.assertFalse(is_valid_id(None))


class RouteIntentTests(unittest.TestCase):
    def test_pregunta_por_nombre_simple(self):
        routed = route("¿Quién es Ana Torres?")
        self.assertEqual(routed.intent, Intent.PATIENT_BY_NAME)
        self.assertEqual(routed.patientName, "Ana Torres")

    def test_pregunta_por_planes_de_un_paciente(self):
        routed = route("¿Qué planes tiene María González?")
        self.assertEqual(routed.intent, Intent.PATIENT_PLANS)
        self.assertEqual(routed.patientName, "María González")

    def test_nunca_produce_get_patient_con_nombre(self):
        """Caso real reportado en producción: el router jamás debe intentar
        resolver un nombre como si fuera un id de paciente."""
        routed = route("¿Qué planes tiene María González?")
        self.assertIsNone(routed.planIdA)
        self.assertEqual(routed.intent, Intent.PATIENT_PLANS)

    def test_pregunta_por_consultas_de_un_paciente(self):
        routed = route("¿Qué consultas tiene Carlos Ruiz?")
        self.assertEqual(routed.intent, Intent.PATIENT_CONSULTATIONS)
        self.assertEqual(routed.patientName, "Carlos Ruiz")

    def test_pregunta_por_calculo_de_un_paciente(self):
        routed = route("¿Cuántas calorías necesita Laura Méndez?")
        self.assertEqual(routed.intent, Intent.CONSULTATION_CALCULATION)
        self.assertEqual(routed.patientName, "Laura Méndez")

    def test_plan_detail_por_contexto_de_navegacion(self):
        routed = route("¿Cuántas calorías tiene este plan?", _ctx(planId="p1"))
        self.assertEqual(routed.intent, Intent.PLAN_DETAIL)
        self.assertEqual(routed.planIdA, "p1")

    def test_plan_validaciones_por_contexto(self):
        routed = route("¿Qué validaciones tiene el plan actual?", _ctx(planId="p1"))
        self.assertEqual(routed.intent, Intent.PLAN_VALIDATIONS)

    def test_plan_aprobacion_por_contexto(self):
        routed = route("¿Se puede aprobar este plan?", _ctx(planId="p1"))
        self.assertEqual(routed.intent, Intent.PLAN_APPROVAL_STATUS)
        self.assertEqual(routed.planIdA, "p1")

    def test_plan_aprobacion_prioriza_sobre_nombre_de_otro_paciente(self):
        """Si hay un plan abierto en el contexto y la pregunta usa palabras de
        aprobación, el contexto de navegación manda, aunque el mensaje
        contenga un nombre propio incidental."""
        routed = route("¿Puede aprobarse este plan, Doctora Ana?", _ctx(planId="p1"))
        self.assertEqual(routed.intent, Intent.PLAN_APPROVAL_STATUS)

    def test_comparacion_de_versiones_con_dos_ids(self):
        id_a = "47c0bccf-420c-4685-9141-84f90f89ebb0"
        id_b = "58d1ccdf-531d-5796-a252-95fa1f8afc41"
        routed = route(f"¿Cuál es la diferencia entre el plan {id_a} y el plan {id_b}?")
        self.assertEqual(routed.intent, Intent.PLAN_COMPARISON)
        self.assertEqual(routed.planIdA, id_a)
        self.assertEqual(routed.planIdB, id_b)
        self.assertTrue(routed.wantsExplanation)

    def test_comparacion_sin_dos_ids_no_se_reconoce(self):
        routed = route("¿Cuál es la diferencia entre este plan y el anterior?")
        self.assertNotEqual(routed.intent, Intent.PLAN_COMPARISON)

    def test_conteo_de_planes_por_estado(self):
        routed = route("¿Cuántos planes están aprobados?")
        self.assertEqual(routed.intent, Intent.PLAN_COUNT_BY_STATUS)
        self.assertEqual(routed.statusFilter, "APPROVED")

    def test_conteo_de_planes_sin_estado_especifico(self):
        routed = route("¿Cuántos planes hay en total?")
        self.assertEqual(routed.intent, Intent.PLAN_COUNT_BY_STATUS)
        self.assertIsNone(routed.statusFilter)

    def test_pacientes_por_estado_de_plan(self):
        routed = route("¿Qué pacientes tienen planes en revisión?")
        self.assertEqual(routed.intent, Intent.PATIENTS_BY_PLAN_STATUS)
        self.assertEqual(routed.statusFilter, "UNDER_REVIEW")

    def test_listar_fuentes_documentales(self):
        routed = route("¿Qué fuentes documentales están disponibles?")
        self.assertEqual(routed.intent, Intent.LIST_KNOWLEDGE_SOURCES)

    def test_busqueda_documental(self):
        routed = route("¿Qué dicen las fuentes sobre fibra dietética?")
        self.assertEqual(routed.intent, Intent.KNOWLEDGE_SEARCH)
        self.assertIn("fibra", routed.knowledgeQuery)

    def test_saludo_va_a_general_assistant(self):
        routed = route("hola, ¿cómo estás?")
        self.assertEqual(routed.intent, Intent.GENERAL_ASSISTANT)

    def test_mensaje_vacio_no_lanza_excepcion(self):
        routed = route("")
        self.assertEqual(routed.intent, Intent.GENERAL_ASSISTANT)

    def test_contexto_none_no_lanza_excepcion(self):
        routed = route("¿cómo estás?", None)
        self.assertEqual(routed.intent, Intent.GENERAL_ASSISTANT)

    def test_deteccion_de_solicitud_de_explicacion(self):
        routed = route("Explica por qué es importante este cálculo para Ana Gómez")
        self.assertTrue(routed.wantsExplanation)


if __name__ == "__main__":
    unittest.main()
