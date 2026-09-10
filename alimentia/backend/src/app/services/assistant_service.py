"""
AlimentiaAssistantService — asistente conversacional híbrido (corrección
post-lanzamiento).

Causa raíz corregida: la primera versión pedía al LLM, en TODAS las
preguntas, decidir qué herramienta usar (1 inferencia real) y luego redactar
la respuesta (2ª inferencia real) — ~180s cada una. Además, el LLM a veces
elegía mal la herramienta (`get_patient("María González")`, usando un
nombre como id), lo que producía un `ToolError` y terminaba en el mensaje de
fallback genérico.

Arquitectura nueva:

    pregunta -> AssistantIntentRouter (determinístico, sin LLM)
             -> herramientas AlimentIA (repositorios existentes)
             -> datos estructurados
             -> formatter determinístico (texto final, sin LLM)
             -> [opcional] 1 sola llamada LLM para explicar/sintetizar
             -> respuesta

Para las intenciones conocidas, el LLM deja de decidir qué herramienta usar
-nunca se le pregunta-. Solo se le llama, como máximo una vez, cuando de
verdad aporta valor (explicación pedida explícitamente, síntesis de RAG, o
narrativa de comparación de versiones). El bucle LLM->tool->LLM original se
conserva íntegro, pero solo como `GENERAL_ASSISTANT` (fallback para
preguntas que el router no reconoce, sección 8).
"""
import json
import time
from dataclasses import dataclass, field

from app.repositories import assistant as assistant_repo
from app.schemas.assistant import (
    AssistantChatRequest, AssistantChatResponse, AssistantDecision, AssistantExplanation,
    AssistantResponseMetadata, AssistantSourceCitation, ToolName,
)
from app.services import assistant_formatters as fmt
from app.services import assistant_router
from app.services import assistant_tools
from app.services.assistant_router import Intent, RoutedQuestion
from app.services.assistant_tools import ToolError
from app.services.llm_client import LLMClient, LLMGenerationError

ALIMENTIA_ASSISTANT_PROMPT_VERSION = "1.0"
MAX_TOOL_ITERATIONS = 5
NO_ANSWER_MESSAGE = "No tengo información suficiente en AlimentIA para responder con precisión a esa pregunta."
NO_SOURCES_MESSAGE = "No hay fuentes documentales configuradas actualmente para responder esta pregunta."
UNAVAILABLE_MESSAGE = "No fue posible consultar al asistente en este momento."
ITERATION_LIMIT_MESSAGE = "No fue posible resolver la pregunta con la información disponible en este momento; intenta reformularla o sé más específico."

# Solo estas intenciones deterministas admiten una explicación LLM opcional
# (sección 17): "explícame" / "qué significa" / "por qué es importante".
_EXPLAINABLE_INTENTS = {
    Intent.PLAN_APPROVAL_STATUS, Intent.PLAN_VALIDATIONS, Intent.CONSULTATION_CALCULATION,
    Intent.PATIENT_BY_NAME, Intent.PLAN_DETAIL,
}

EXPLAIN_SYSTEM_PROMPT = """Eres el asistente de inteligencia artificial de AlimentIA.

Se te dan hechos YA VERIFICADOS por AlimentIA (motor determinístico, base de datos o documentos autorizados). Tu única tarea es explicarlos de forma clara, breve y profesional para un nutriólogo.

Nunca contradigas los hechos que se te dan. Nunca inventes datos adicionales, alimentos, cálculos ni fuentes que no estén en los hechos. Si los hechos no bastan para responder algo, dilo explícitamente en vez de inventarlo.

No diagnostiques enfermedades. No sustituyas el criterio del profesional de nutrición. No apruebes ni rechaces planes.

Responde SIEMPRE con un JSON que cumpla exactamente este formato, sin texto adicional ni bloques de markdown: {"answer": "<tu explicación>"}"""


TOOL_REGISTRY: dict[ToolName, dict] = {
    ToolName.GET_PATIENT: {"fn": assistant_tools.get_patient_tool, "params": ["patient_id"],
        "description": "Resumen de un paciente (nombre, sexo, edad, objetivo habitual, condiciones) por su id."},
    ToolName.SEARCH_PATIENTS: {"fn": assistant_tools.search_patients_tool, "params": ["query"],
        "description": "Busca pacientes por nombre (coincidencia parcial). Úsala cuando el usuario mencione un nombre en vez de un id."},
    ToolName.GET_PATIENT_CONSULTATIONS: {"fn": assistant_tools.get_patient_consultations_tool, "params": ["patient_id"],
        "description": "Lista las consultas nutricionales de un paciente, con sus objetivos calculados."},
    ToolName.GET_CONSULTATION: {"fn": assistant_tools.get_consultation_tool, "params": ["consultation_id"],
        "description": "Detalle de una consulta específica por id."},
    ToolName.GET_CONSULTATION_CALCULATION: {"fn": assistant_tools.get_consultation_calculation_tool, "params": ["consultation_id"],
        "description": "Detalle del cálculo determinístico (BMR, TDEE, factor de actividad, ajuste, macros) de una consulta."},
    ToolName.GET_PATIENT_PLANS: {"fn": assistant_tools.get_patient_plans_tool, "params": ["patient_id"],
        "description": "Lista todos los planes (todas las versiones, todas las consultas) de un paciente."},
    ToolName.GET_CONSULTATION_PLANS: {"fn": assistant_tools.get_consultation_plans_tool, "params": ["consultation_id"],
        "description": "Lista las versiones de plan de una consulta específica."},
    ToolName.GET_PLAN: {"fn": assistant_tools.get_plan_tool, "params": ["plan_id"],
        "description": "Detalle completo de un plan: estado, energía, comidas, alimentos, validaciones y fuentes."},
    ToolName.GET_PLAN_VALIDATIONS: {"fn": assistant_tools.get_plan_validations_tool, "params": ["plan_id"],
        "description": "Solo las validaciones (bloqueantes/advertencias/informativas) de un plan."},
    ToolName.GET_PLAN_SOURCES: {"fn": assistant_tools.get_plan_sources_tool, "params": ["plan_id"],
        "description": "Solo las fuentes documentales realmente recuperadas para un plan."},
    ToolName.COMPARE_PLAN_VERSIONS: {"fn": assistant_tools.compare_plan_versions_tool, "params": ["plan_id_a", "plan_id_b"],
        "description": "Compara dos versiones de plan (por id) de forma determinística: estado, energía, alimentos agregados/quitados, cantidades, validaciones."},
    ToolName.SEARCH_KNOWLEDGE: {"fn": assistant_tools.search_knowledge_tool, "params": ["query"],
        "description": "Busca en los documentos autorizados (RAG) fragmentos relevantes a una pregunta documental."},
    ToolName.LIST_KNOWLEDGE_SOURCES: {"fn": assistant_tools.list_knowledge_sources_tool, "params": [],
        "description": "Lista todas las fuentes documentales autorizadas registradas en el sistema."},
    ToolName.COUNT_PLANS_BY_STATUS: {"fn": assistant_tools.count_plans_by_status_tool, "params": [],
        "description": "Cuenta cuántos planes existen por cada estado (DRAFT, UNDER_REVIEW, APPROVED, REJECTED, etc.)."},
    ToolName.LIST_PATIENTS_BY_PLAN_STATUS: {"fn": assistant_tools.list_patients_by_plan_status_tool, "params": ["status"],
        "description": "Lista pacientes cuyo plan tiene un estado dado (por ejemplo UNDER_REVIEW o APPROVED)."},
}
_ID_PARAMS = {"patient_id", "consultation_id", "plan_id", "plan_id_a", "plan_id_b"}


def _tools_description() -> str:
    return "\n".join(
        f"- {name.value}({', '.join(meta['params']) or 'sin parámetros'}): {meta['description']}"
        for name, meta in TOOL_REGISTRY.items())


SYSTEM_PROMPT = f"""Eres el asistente de inteligencia artificial de AlimentIA.

Tu función es ayudar a profesionales de nutrición a consultar y comprender información almacenada en AlimentIA: pacientes, consultas, cálculos nutricionales, planes, versiones, alimentos, validaciones y fuentes documentales autorizadas.

Utiliza las herramientas disponibles para recuperar información antes de responder. Nunca inventes datos de pacientes, planes, cálculos o documentos. Si la información no existe, indícalo claramente.

Distingue entre: datos registrados en AlimentIA, resultados calculados por AlimentIA, contenido recuperado de documentos, y explicaciones generadas por ti.

No diagnostiques enfermedades. No sustituyas el criterio del profesional de nutrición. No apruebes ni rechaces planes. No modifiques información. No inventes fuentes bibliográficas.

Cuando una afirmación provenga de documentos, utiliza únicamente las fuentes recuperadas por las herramientas. Cuando una pregunta pueda responderse con datos estructurados, utiliza esos datos en lugar de inferir la respuesta.

IMPORTANTE: si la pregunta menciona el nombre de un paciente (no un id), tu primer paso SIEMPRE debe ser "search_patients" con ese nombre. Nunca uses "get_patient" con un nombre como argumento: get_patient solo acepta un id real.

Responde de forma clara, breve y profesional.

Herramientas disponibles (usa exactamente estos nombres; nunca generes SQL ni inventes otra herramienta):
{_tools_description()}

Responde SIEMPRE con un JSON que cumpla exactamente este formato, sin texto adicional ni bloques de markdown:
{{"action": "use_tool" | "answer" | "ask_clarification", "tool": "<nombre_de_herramienta>" o null, "arguments": {{"parametro": "valor"}}, "answer": "<texto>" o null}}

- "use_tool": cuando necesites recuperar información antes de responder. Incluye "tool" y "arguments" (los ids/valores exactos que ya conozcas del contexto o de resultados previos).
- "answer": cuando ya tengas la información necesaria (de herramientas ya ejecutadas en este turno) o la pregunta no requiera datos de AlimentIA. Incluye la respuesta completa en "answer".
- "ask_clarification": únicamente cuando existan varias coincidencias (por ejemplo, varios pacientes con el mismo nombre) y no puedas elegir sin adivinar. Incluye la pregunta de aclaración en "answer".

Nunca uses la misma herramienta con los mismos argumentos dos veces en la misma conversación."""


def _to_jsonable(value):
    if isinstance(value, list):
        return [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in value]
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _summarize_result(tool: ToolName, result) -> tuple[str, list[AssistantSourceCitation], dict | None]:
    """Serializa el resultado para dárselo de vuelta al LLM (solo en el
    fallback GENERAL_ASSISTANT), y extrae -sin pasar por el LLM- las fuentes
    y los hechos estructurados relevantes para el "grounding": esos dos
    nunca se derivan del texto libre del modelo, siempre de lo que la
    herramienta realmente devolvió."""
    text = json.dumps(_to_jsonable(result), ensure_ascii=False)[:4000]
    sources: list[AssistantSourceCitation] = []
    structured: dict | None = None

    if tool == ToolName.GET_PLAN:
        sources = [AssistantSourceCitation(sourceId=s.knowledgeSourceId, documentName=s.documentName, institution=s.institution)
                   for s in result.sources]
        structured = {"planStatus": result.status, "blockingValidationCount": result.blockingValidationCount,
                      "canApprove": result.blockingValidationCount == 0, "totalCalories": result.totalCalories,
                      "targetCalories": result.targetCalories}
    elif tool == ToolName.GET_PLAN_SOURCES:
        sources = [AssistantSourceCitation(sourceId=s.knowledgeSourceId, documentName=s.documentName, institution=s.institution)
                   for s in result]
    elif tool == ToolName.GET_PLAN_VALIDATIONS:
        blocking = sum(1 for v in result if v.isBlocking)
        structured = {"blockingValidationCount": blocking, "canApprove": blocking == 0}
    elif tool == ToolName.SEARCH_KNOWLEDGE:
        sources = [AssistantSourceCitation(sourceId=c.sourceId, documentName=c.documentName, institution=c.institution)
                   for c in result]
    elif tool == ToolName.GET_CONSULTATION_CALCULATION:
        structured = {"targetCalories": result.targetCalories, "basalMetabolicRate": result.basalMetabolicRate,
                      "totalEnergyExpenditure": result.totalEnergyExpenditure}

    return text, sources, structured


def _apply_grounding(answer: str, structured: dict | None) -> str:
    """Antepone hechos verificados directamente de la base de datos (nunca
    redactados por el LLM) cuando existen, para que la respuesta final nunca
    contradiga el estado estructurado real."""
    if not structured:
        return answer
    facts = []
    if structured.get("targetCalories") is not None:
        facts.append(f"Energía objetivo registrada en AlimentIA: {structured['targetCalories']:.0f} kcal.")
    if "blockingValidationCount" in structured:
        n = structured["blockingValidationCount"]
        facts.append(f"Estado verificado: este plan tiene {n} validación(es) bloqueante(s) y no puede aprobarse todavía."
                      if n > 0 else "Estado verificado: este plan no tiene validaciones bloqueantes pendientes.")
    if not facts:
        return answer
    prefix = " ".join(facts)
    return f"{prefix}\n\n{answer}" if answer else prefix


def _build_user_prompt(request: AssistantChatRequest, observations: list[str]) -> str:
    context = request.context
    lines = [
        "Contexto de navegación actual (solo para resolver referencias como 'este paciente' o 'este plan'; nunca asumas datos que no estén aquí o en los resultados de herramientas):",
        f"- ruta: {context.route or 'desconocida'}",
        f"- patientId: {context.patientId or 'ninguno'}",
        f"- consultationId: {context.consultationId or 'ninguno'}",
        f"- planId: {context.planId or 'ninguno'}",
    ]
    if request.conversation:
        lines.append("\nConversación previa (más reciente al final):")
        lines.extend(f"{turn.role}: {turn.content}" for turn in request.conversation[-6:])
    lines.append(f"\nPregunta del profesional: {request.message}")
    if observations:
        lines.append("\nResultados de herramientas ya ejecutadas en este turno:")
        lines.extend(observations)
        lines.append("\nCon esta información, decide: responder ahora (action=answer), pedir una aclaración "
                      "(action=ask_clarification) o usar otra herramienta distinta si de verdad falta información "
                      "(action=use_tool). No repitas una herramienta ya usada con los mismos argumentos.")
    else:
        lines.append("\nDecide qué herramienta usar para responder, o responde directamente (action=answer) "
                      "si la pregunta no requiere consultar información de AlimentIA (por ejemplo, un saludo).")
    return "\n".join(lines)


@dataclass
class _Outcome:
    answer: str
    tools_used: list[str] = field(default_factory=list)
    sources: list[AssistantSourceCitation] = field(default_factory=list)
    structured_data: dict | None = None
    response_mode: str = "deterministic"
    llm_time_ms: int = 0
    # True = mensaje de control (no encontrado / ambiguo / sin fuentes): no
    # tiene sentido pedirle al LLM que lo "explique" después.
    final: bool = False


class AlimentiaAssistantService:
    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client or LLMClient()

    # --- Orquestación --------------------------------------------------

    async def chat(self, db, request: AssistantChatRequest) -> AssistantChatResponse:
        started = time.monotonic()
        routed = assistant_router.route(request.message, request.context)
        routing_time_ms = int((time.monotonic() - started) * 1000)

        status, error_message = "SUCCESS", None
        handler_started = time.monotonic()
        try:
            outcome = await self._dispatch(db, routed, request)
            if (routed.intent in _EXPLAINABLE_INTENTS and routed.wantsExplanation
                    and not outcome.final and outcome.response_mode == "deterministic"):
                outcome = await self._maybe_explain(outcome, request.message)
        except Exception as exc:  # noqa: BLE001 - nunca exponer stack traces (sección 38)
            status, error_message = "FAILED", str(exc)
            outcome = _Outcome(answer=UNAVAILABLE_MESSAGE, final=True)
        handler_time_ms = int((time.monotonic() - handler_started) * 1000)
        tool_execution_time_ms = max(handler_time_ms - outcome.llm_time_ms, 0)

        execution_ms = int((time.monotonic() - started) * 1000)
        try:
            await assistant_repo.log_interaction(db, prompt_version=ALIMENTIA_ASSISTANT_PROMPT_VERSION,
                model=self.llm_client.model, user_question=request.message,
                navigation_context=request.context.model_dump(), tools_used=outcome.tools_used,
                source_ids=[source.sourceId for source in outcome.sources],
                execution_time_ms=execution_ms, status=status, error_message=error_message)
        except Exception:
            pass  # la trazabilidad nunca debe impedir responder al usuario.

        return AssistantChatResponse(
            answer=outcome.answer, toolsUsed=outcome.tools_used, sources=outcome.sources,
            structuredData=outcome.structured_data,
            metadata=AssistantResponseMetadata(
                model=self.llm_client.model, promptVersion=ALIMENTIA_ASSISTANT_PROMPT_VERSION,
                executionTimeMs=execution_ms, toolIterations=len(outcome.tools_used),
                routingTimeMs=routing_time_ms, toolExecutionTimeMs=tool_execution_time_ms,
                llmExecutionTimeMs=outcome.llm_time_ms, responseMode=outcome.response_mode))

    async def _dispatch(self, db, routed: RoutedQuestion, request: AssistantChatRequest) -> _Outcome:
        handlers = {
            Intent.PATIENT_BY_NAME: self._handle_patient_by_name,
            Intent.PATIENT_PLANS: self._handle_patient_plans,
            Intent.PATIENT_CONSULTATIONS: self._handle_patient_consultations,
            Intent.PLAN_DETAIL: self._handle_plan_detail,
            Intent.PLAN_VALIDATIONS: self._handle_plan_validations,
            Intent.PLAN_APPROVAL_STATUS: self._handle_plan_approval,
            Intent.PLAN_COMPARISON: self._handle_plan_comparison,
            Intent.CONSULTATION_CALCULATION: self._handle_consultation_calculation,
            Intent.PLAN_COUNT_BY_STATUS: self._handle_plan_counts,
            Intent.PATIENTS_BY_PLAN_STATUS: self._handle_patients_by_status,
            Intent.KNOWLEDGE_SEARCH: self._handle_knowledge_search,
            Intent.LIST_KNOWLEDGE_SOURCES: self._handle_list_sources,
        }
        handler = handlers.get(routed.intent)
        if handler is None:
            return await self._handle_general(db, request)
        return await handler(db, routed)

    # --- Resolución de pacientes por nombre (sección 4/10) --------------

    async def _resolve_patient(self, db, name: str | None) -> tuple[str | None, _Outcome | None]:
        if not name:
            return None, _Outcome(answer=NO_ANSWER_MESSAGE, final=True)
        matches = await assistant_tools.search_patients_tool(db, name)
        if not matches:
            return None, _Outcome(answer=fmt.format_patient_not_found(name), tools_used=["search_patients"], final=True)
        if len(matches) > 1:
            return None, _Outcome(answer=fmt.format_multiple_patients(name, matches), tools_used=["search_patients"], final=True)
        return matches[0].id, None

    # --- Handlers deterministas ------------------------------------------

    async def _handle_patient_by_name(self, db, routed: RoutedQuestion) -> _Outcome:
        patient_id, error = await self._resolve_patient(db, routed.patientName)
        if error:
            return error
        patient = await assistant_tools.get_patient_tool(db, patient_id)
        return _Outcome(answer=fmt.format_patient_summary(patient), tools_used=["search_patients", "get_patient"])

    async def _handle_patient_plans(self, db, routed: RoutedQuestion) -> _Outcome:
        patient_id, error = await self._resolve_patient(db, routed.patientName)
        if error:
            return error
        patient = await assistant_tools.get_patient_tool(db, patient_id)
        plans = await assistant_tools.get_patient_plans_tool(db, patient_id)
        return _Outcome(answer=fmt.format_patient_plans(patient.name, plans),
            tools_used=["search_patients", "get_patient", "get_patient_plans"])

    async def _handle_patient_consultations(self, db, routed: RoutedQuestion) -> _Outcome:
        patient_id, error = await self._resolve_patient(db, routed.patientName)
        if error:
            return error
        patient = await assistant_tools.get_patient_tool(db, patient_id)
        consultations = await assistant_tools.get_patient_consultations_tool(db, patient_id)
        return _Outcome(answer=fmt.format_patient_consultations(patient.name, consultations),
            tools_used=["search_patients", "get_patient", "get_patient_consultations"])

    async def _handle_consultation_calculation(self, db, routed: RoutedQuestion) -> _Outcome:
        patient_id, error = await self._resolve_patient(db, routed.patientName)
        if error:
            return error
        patient = await assistant_tools.get_patient_tool(db, patient_id)
        consultations = await assistant_tools.get_patient_consultations_tool(db, patient_id)
        tools_used = ["search_patients", "get_patient", "get_patient_consultations"]
        if not consultations:
            return _Outcome(answer=f"{patient.name} todavía no tiene ninguna consulta registrada.",
                tools_used=tools_used, final=True)
        latest = sorted(consultations, key=lambda c: c.consultationDate, reverse=True)[0]
        try:
            calculation = await assistant_tools.get_consultation_calculation_tool(db, latest.id)
        except ToolError:
            return _Outcome(answer=f"La consulta más reciente de {patient.name} todavía no tiene un cálculo nutricional registrado.",
                tools_used=tools_used, final=True)
        structured = {"targetCalories": calculation.targetCalories, "basalMetabolicRate": calculation.basalMetabolicRate,
                      "totalEnergyExpenditure": calculation.totalEnergyExpenditure}
        return _Outcome(answer=fmt.format_calculation_summary(patient.name, calculation),
            tools_used=[*tools_used, "get_consultation_calculation"], structured_data=structured)

    async def _handle_plan_detail(self, db, routed: RoutedQuestion) -> _Outcome:
        if not assistant_router.is_valid_id(routed.planIdA):
            return _Outcome(answer=NO_ANSWER_MESSAGE, final=True)
        try:
            plan = await assistant_tools.get_plan_tool(db, routed.planIdA)
        except ToolError as exc:
            return _Outcome(answer=str(exc), tools_used=["get_plan"], final=True)
        sources = [AssistantSourceCitation(sourceId=s.knowledgeSourceId, documentName=s.documentName, institution=s.institution)
                   for s in plan.sources]
        structured = {"planStatus": plan.status, "totalCalories": plan.totalCalories, "targetCalories": plan.targetCalories,
                      "blockingValidationCount": plan.blockingValidationCount, "canApprove": plan.blockingValidationCount == 0}
        return _Outcome(answer=fmt.format_plan_detail(plan), tools_used=["get_plan"], sources=sources, structured_data=structured)

    async def _handle_plan_validations(self, db, routed: RoutedQuestion) -> _Outcome:
        if not assistant_router.is_valid_id(routed.planIdA):
            return _Outcome(answer=NO_ANSWER_MESSAGE, final=True)
        try:
            plan = await assistant_tools.get_plan_tool(db, routed.planIdA)
        except ToolError as exc:
            return _Outcome(answer=str(exc), tools_used=["get_plan"], final=True)
        structured = {"blockingValidationCount": plan.blockingValidationCount, "canApprove": plan.blockingValidationCount == 0}
        return _Outcome(answer=fmt.format_plan_validations(plan), tools_used=["get_plan"], structured_data=structured)

    async def _handle_plan_approval(self, db, routed: RoutedQuestion) -> _Outcome:
        if not assistant_router.is_valid_id(routed.planIdA):
            return _Outcome(answer=NO_ANSWER_MESSAGE, final=True)
        try:
            plan = await assistant_tools.get_plan_tool(db, routed.planIdA)
        except ToolError as exc:
            return _Outcome(answer=str(exc), tools_used=["get_plan"], final=True)
        # Sección 16: la respuesta se basa exclusivamente en las validaciones
        # bloqueantes reales; el LLM (si se llega a usar para explicar) nunca
        # puede contradecir este veredicto porque no participa en calcularlo.
        structured = {"planStatus": plan.status, "blockingValidationCount": plan.blockingValidationCount,
                      "canApprove": plan.blockingValidationCount == 0}
        return _Outcome(answer=fmt.format_plan_approval_status(plan), tools_used=["get_plan"], structured_data=structured)

    async def _handle_plan_comparison(self, db, routed: RoutedQuestion) -> _Outcome:
        if not (assistant_router.is_valid_id(routed.planIdA) and assistant_router.is_valid_id(routed.planIdB)):
            return _Outcome(answer=NO_ANSWER_MESSAGE, final=True)
        try:
            comparison = await assistant_tools.compare_plan_versions_tool(db, routed.planIdA, routed.planIdB)
        except ToolError as exc:
            return _Outcome(answer=str(exc), tools_used=["compare_plan_versions"], final=True)
        outcome = _Outcome(answer=fmt.format_plan_comparison(comparison), tools_used=["compare_plan_versions"])
        # La comparación siempre se narra (sección 7): una sola llamada LLM.
        return await self._maybe_explain(outcome, "Explica esta comparación de versiones de forma breve.")

    async def _handle_plan_counts(self, db, routed: RoutedQuestion) -> _Outcome:
        counts = await assistant_tools.count_plans_by_status_tool(db)
        if routed.statusFilter:
            counts = [c for c in counts if c.status == routed.statusFilter]
        return _Outcome(answer=fmt.format_plan_counts(counts), tools_used=["count_plans_by_status"])

    async def _handle_patients_by_status(self, db, routed: RoutedQuestion) -> _Outcome:
        status = routed.statusFilter or "APPROVED"
        rows = await assistant_tools.list_patients_by_plan_status_tool(db, status)
        return _Outcome(answer=fmt.format_patients_by_status(status, rows), tools_used=["list_patients_by_plan_status"])

    async def _handle_list_sources(self, db, routed: RoutedQuestion) -> _Outcome:
        sources = await assistant_tools.list_knowledge_sources_tool(db)
        return _Outcome(answer=fmt.format_knowledge_sources(sources), tools_used=["list_knowledge_sources"])

    async def _handle_knowledge_search(self, db, routed: RoutedQuestion) -> _Outcome:
        chunks = await assistant_tools.search_knowledge_tool(db, routed.knowledgeQuery)
        if not chunks:
            # Sección 15: nunca se llama a Ollama solo para decir que no hay fuentes.
            return _Outcome(answer=NO_SOURCES_MESSAGE, tools_used=["search_knowledge"], final=True)
        sources = [AssistantSourceCitation(sourceId=c.sourceId, documentName=c.documentName, institution=c.institution)
                   for c in chunks]
        context_text = "\n\n".join(f"[{c.documentName}] {c.content}" for c in chunks)
        prompt = (f"Fragmentos documentales recuperados (usa SOLO esta información, nunca la combines con "
                  f"conocimiento general ni inventes otra fuente):\n{context_text}\n\n"
                  f"Pregunta: {routed.knowledgeQuery}\n\n"
                  "Responde de forma breve y profesional citando de qué documento proviene cada idea relevante.")
        started = time.monotonic()
        try:
            explanation, _raw = await self.llm_client.generate_structured(
                system_prompt=EXPLAIN_SYSTEM_PROMPT, user_prompt=prompt, response_model=AssistantExplanation)
            llm_time_ms = int((time.monotonic() - started) * 1000)
            answer = (explanation.answer or "").strip() or NO_ANSWER_MESSAGE
            return _Outcome(answer=answer, tools_used=["search_knowledge"], sources=sources,
                response_mode="llm", llm_time_ms=llm_time_ms)
        except LLMGenerationError:
            # El LLM no respondió: los fragmentos reales igual son una respuesta válida (nunca un 500).
            fallback = "\n\n".join(f"Según {c.documentName}: {c.content[:300]}" for c in chunks)
            return _Outcome(answer=fallback, tools_used=["search_knowledge"], sources=sources)

    async def _maybe_explain(self, outcome: _Outcome, question: str) -> _Outcome:
        """Sección 17: una única llamada LLM opcional para explicar hechos ya
        calculados. Nunca se le pide al LLM que decida qué herramienta usar
        ni que recalcule nada; solo redacta a partir de `outcome.answer`."""
        prompt = (f"Hechos verificados de AlimentIA (nunca los contradigas ni inventes otros):\n{outcome.answer}\n\n"
                  f"Pregunta original del profesional: {question}\n\n"
                  "Explica estos hechos de forma clara y breve para un profesional de nutrición. "
                  "No agregues datos que no estén arriba.")
        started = time.monotonic()
        try:
            explanation, _raw = await self.llm_client.generate_structured(
                system_prompt=EXPLAIN_SYSTEM_PROMPT, user_prompt=prompt, response_model=AssistantExplanation)
        except LLMGenerationError:
            # El hecho determinístico ya es una respuesta válida por sí solo;
            # si el LLM falla, no forzamos nada (sección 39).
            return outcome
        llm_time_ms = int((time.monotonic() - started) * 1000)
        explained = (explanation.answer or "").strip()
        combined = f"{outcome.answer}\n\n{explained}" if explained else outcome.answer
        return _Outcome(answer=combined, tools_used=outcome.tools_used, sources=outcome.sources,
            structured_data=outcome.structured_data, response_mode="llm", llm_time_ms=llm_time_ms, final=outcome.final)

    # --- Fallback: bucle LLM->tool->LLM original (solo GENERAL_ASSISTANT) --

    async def _handle_general(self, db, request: AssistantChatRequest) -> _Outcome:
        tools_used: list[str] = []
        used_calls: set[tuple[str, str]] = set()
        source_ids: list[str] = []
        sources: list[AssistantSourceCitation] = []
        structured_data: dict | None = None
        observations: list[str] = []
        llm_time_ms = 0
        answer = ""

        for _ in range(MAX_TOOL_ITERATIONS):
            user_prompt = _build_user_prompt(request, observations)
            llm_started = time.monotonic()
            try:
                decision, _raw = await self.llm_client.generate_structured(
                    system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, response_model=AssistantDecision)
            except LLMGenerationError:
                llm_time_ms += int((time.monotonic() - llm_started) * 1000)
                return _Outcome(answer=UNAVAILABLE_MESSAGE, tools_used=tools_used, sources=sources,
                    structured_data=structured_data, response_mode="llm", llm_time_ms=llm_time_ms, final=True)
            llm_time_ms += int((time.monotonic() - llm_started) * 1000)

            action = (decision.action or "").strip().lower()
            if action in ("answer", "ask_clarification"):
                answer = (decision.answer or "").strip() or NO_ANSWER_MESSAGE
                break
            if action != "use_tool" or decision.tool is None:
                answer = (decision.answer or "").strip() or NO_ANSWER_MESSAGE
                break

            tool_meta = TOOL_REGISTRY.get(decision.tool)
            if tool_meta is None:
                observations.append(f"[{decision.tool}] Herramienta no reconocida; usa solo las herramientas listadas.")
                continue

            call_key = (decision.tool.value, json.dumps(decision.arguments, sort_keys=True))
            if call_key in used_calls:
                observations.append(f"[{decision.tool}] Ya se ejecutó con estos mismos argumentos; usa la información anterior o responde.")
                continue
            used_calls.add(call_key)

            kwargs = {name: (str(value) if (value := decision.arguments.get(name)) is not None else None)
                      for name in tool_meta["params"]}

            # Sección 9/10: recuperación segura del error observado en
            # producción. Si un argumento que debería ser id no lo parece,
            # nunca se ejecuta la herramienta con ese valor; si además la
            # herramienta era get_patient, se redirige automáticamente a
            # search_patients (exactamente el caso real reportado).
            bad_id_params = [p for p in tool_meta["params"]
                              if p in _ID_PARAMS and kwargs.get(p) and not assistant_router.is_valid_id(kwargs[p])]
            if bad_id_params:
                candidate = kwargs[bad_id_params[0]]
                if decision.tool == ToolName.GET_PATIENT:
                    matches = await assistant_tools.search_patients_tool(db, candidate)
                    tools_used.append("search_patients")
                    if len(matches) == 1:
                        observations.append(f'[search_patients] "{candidate}" se interpretó como nombre; paciente encontrado: '
                                             f"{json.dumps(matches[0].model_dump(mode='json'), ensure_ascii=False)}")
                    elif not matches:
                        observations.append(f'[search_patients] No se encontró ningún paciente llamado "{candidate}".')
                    else:
                        names = ", ".join(match.name for match in matches)
                        observations.append(f'[search_patients] Hay {len(matches)} pacientes que coinciden con '
                                             f'"{candidate}": {names}. Responde pidiendo aclaración (action=ask_clarification).')
                else:
                    observations.append(f"[{decision.tool}] El valor '{candidate}' no tiene forma de id; "
                                         "usa search_patients primero si es un nombre, o pide aclaración.")
                continue

            tools_used.append(decision.tool.value)
            try:
                result = await tool_meta["fn"](db, **kwargs)
            except ToolError as exc:
                observations.append(f"[{decision.tool}] {exc}")
                continue

            if decision.tool == ToolName.SEARCH_KNOWLEDGE and not result:
                answer = NO_SOURCES_MESSAGE
                break

            text, extracted_sources, extracted_structured = _summarize_result(decision.tool, result)
            observations.append(f"[{decision.tool}] {text}")
            for source in extracted_sources:
                if source.sourceId not in source_ids:
                    source_ids.append(source.sourceId)
                    sources.append(source)
            if extracted_structured is not None:
                structured_data = extracted_structured
        else:
            answer = ITERATION_LIMIT_MESSAGE

        if answer != NO_SOURCES_MESSAGE:
            answer = _apply_grounding(answer, structured_data)
        return _Outcome(answer=answer, tools_used=tools_used, sources=sources, structured_data=structured_data,
            response_mode="llm", llm_time_ms=llm_time_ms)
