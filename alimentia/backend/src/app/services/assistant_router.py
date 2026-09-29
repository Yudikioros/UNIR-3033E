"""Clasifica preguntas conocidas sin invocar el modelo de lenguaje."""
import re
from enum import StrEnum

from pydantic import Field

from app.schemas.assistant import AssistantNavigationContext
from app.schemas.persistence import Contract

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

_NAME_TRIGGER_RE = re.compile(
    r"\b(?:de|del|tiene|paciente|sobre)\s+([A-ZÁÉÍÓÚÑ][\wÀ-ÿ'-]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÀ-ÿ'-]*){0,3})")
_NAME_FALLBACK_RE = re.compile(
    r"([A-ZÁÉÍÓÚÑ][\wÀ-ÿ'-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÀ-ÿ'-]+)+)")

_PLAN_CONTEXT_TRIGGERS = ("este plan", "el plan actual",
                          "plan actual", "esta versión", "esta version")
_APPROVAL_KEYWORDS = ("aprobar", "aprobación", "aprobacion", "aprobarse")
_VALIDATION_KEYWORDS = ("validacion", "validación", "validaciones")
_ENERGY_KEYWORDS = ("caloría", "calorías", "caloria", "calorias",
                    "kcal", "energía", "energia", "energético", "energetico")
_FOOD_KEYWORDS = ("aliment", "comida", "comidas",
                  "qué contiene", "que contiene")
_EXPLAIN_KEYWORDS = ("explíca", "explica", "qué significa",
                     "que significa", "por qué es importante", "por que es importante")
_COMPARISON_KEYWORDS = ("diferencia", "comparar", "compara",
                        "cambios respecto", "cambió", "cambio")
_COUNT_KEYWORDS = ("cuántos", "cuantos", "cuántas", "cuantas")
_STATUS_QUESTION_KEYWORDS = (
    "qué pacientes", "que pacientes", "cuáles pacientes", "cuales pacientes")
_KNOWLEDGE_LIST_KEYWORDS = ("qué fuentes", "que fuentes", "qué documentos", "que documentos",
                            "fuentes disponibles", "documentos disponibles", "fuentes documentales")
_KNOWLEDGE_SEARCH_TRIGGERS = ("sobre", "acerca de")
_KNOWLEDGE_SEARCH_KEYWORDS = (
    "dicen las fuentes", "documento respalda", "qué dice", "que dice")

_STATUS_WORDS = {
    "aprobados": "APPROVED", "aprobado": "APPROVED", "aprobación": "APPROVED",
    "rechazados": "REJECTED", "rechazado": "REJECTED",
    "revisión": "UNDER_REVIEW", "revision": "UNDER_REVIEW", "pendientes": "UNDER_REVIEW", "pendiente": "UNDER_REVIEW",
    "borradores": "DRAFT", "borrador": "DRAFT",
}


class Intent(StrEnum):
    PATIENT_BY_NAME = "PATIENT_BY_NAME"
    PATIENT_PLANS = "PATIENT_PLANS"
    PATIENT_CONSULTATIONS = "PATIENT_CONSULTATIONS"
    PLAN_DETAIL = "PLAN_DETAIL"
    PLAN_VALIDATIONS = "PLAN_VALIDATIONS"
    PLAN_APPROVAL_STATUS = "PLAN_APPROVAL_STATUS"
    PLAN_COMPARISON = "PLAN_COMPARISON"
    CONSULTATION_CALCULATION = "CONSULTATION_CALCULATION"
    PLAN_COUNT_BY_STATUS = "PLAN_COUNT_BY_STATUS"
    PATIENTS_BY_PLAN_STATUS = "PATIENTS_BY_PLAN_STATUS"
    KNOWLEDGE_SEARCH = "KNOWLEDGE_SEARCH"
    LIST_KNOWLEDGE_SOURCES = "LIST_KNOWLEDGE_SOURCES"
    GENERAL_ASSISTANT = "GENERAL_ASSISTANT"


class RoutedQuestion(Contract):
    intent: Intent
    patientName: str | None = None
    planIdA: str | None = None
    planIdB: str | None = None
    statusFilter: str | None = None
    knowledgeQuery: str | None = None
    wantsExplanation: bool = Field(
        default=False, description="Sección 17: el usuario pidió explícitamente una explicación.")


def is_valid_id(value: str | None) -> bool:
    """Acepta UUID y el prefijo de consulta legacy reconocido."""
    if not value:
        return False
    value = value.strip()
    if " " in value:
        return False
    return bool(_UUID_RE.search(value))


def _extract_name(message: str) -> str | None:
    match = _NAME_TRIGGER_RE.search(message)
    if match:
        return match.group(1).strip().rstrip("?¿.,!¡")
    match = _NAME_FALLBACK_RE.search(message)
    if match:
        return match.group(1).strip().rstrip("?¿.,!¡")
    return None


def _extract_status(message_lower: str) -> str | None:
    for word, status in _STATUS_WORDS.items():
        if word in message_lower:
            return status
    return None


def _extract_topic_after(text: str, lowered: str, triggers: tuple[str, ...]) -> str | None:
    for trigger in triggers:
        idx = lowered.find(trigger)
        if idx >= 0:
            topic = text[idx + len(trigger):].strip(" ?¿.,!¡")
            if topic:
                return topic
    return None


def route(message: str, context: AssistantNavigationContext | None = None) -> RoutedQuestion:
    """Clasifica el mensaje; devuelve `GENERAL_ASSISTANT` si no hay coincidencia."""
    text = (message or "").strip()
    lowered = text.casefold()
    context = context or AssistantNavigationContext()
    wants_explanation = any(
        keyword in lowered for keyword in _EXPLAIN_KEYWORDS)
    name = _extract_name(text)

    # Resuelve referencias al plan visible cuando no se nombra otro paciente.
    plan_id = context.planId
    if plan_id:
        mentions_plan_context = any(
            trigger in lowered for trigger in _PLAN_CONTEXT_TRIGGERS)
        mentions_approval = any(
            keyword in lowered for keyword in _APPROVAL_KEYWORDS)
        mentions_validations = any(
            keyword in lowered for keyword in _VALIDATION_KEYWORDS)
        mentions_plan_detail = not name and (
            any(keyword in lowered for keyword in _ENERGY_KEYWORDS) or any(keyword in lowered for keyword in _FOOD_KEYWORDS))
        if mentions_approval:
            return RoutedQuestion(intent=Intent.PLAN_APPROVAL_STATUS, planIdA=plan_id, wantsExplanation=wants_explanation)
        if mentions_validations:
            return RoutedQuestion(intent=Intent.PLAN_VALIDATIONS, planIdA=plan_id, wantsExplanation=wants_explanation)
        if mentions_plan_context or mentions_plan_detail:
            return RoutedQuestion(intent=Intent.PLAN_DETAIL, planIdA=plan_id, wantsExplanation=wants_explanation)

    # La comparación requiere dos identificadores de plan explícitos.
    if any(keyword in lowered for keyword in _COMPARISON_KEYWORDS):
        ids = _UUID_RE.findall(text)
        if len(ids) >= 2:
            return RoutedQuestion(intent=Intent.PLAN_COMPARISON, planIdA=ids[0], planIdB=ids[1], wantsExplanation=True)

    # Consultas agregadas.
    if any(keyword in lowered for keyword in _COUNT_KEYWORDS) and "plan" in lowered:
        return RoutedQuestion(intent=Intent.PLAN_COUNT_BY_STATUS, statusFilter=_extract_status(lowered))
    if "pacient" in lowered and any(keyword in lowered for keyword in _STATUS_QUESTION_KEYWORDS):
        status = _extract_status(lowered)
        if status:
            return RoutedQuestion(intent=Intent.PATIENTS_BY_PLAN_STATUS, statusFilter=status)

    # Consultas documentales.
    if any(keyword in lowered for keyword in _KNOWLEDGE_LIST_KEYWORDS) and "sobre" not in lowered:
        return RoutedQuestion(intent=Intent.LIST_KNOWLEDGE_SOURCES)
    if any(keyword in lowered for keyword in _KNOWLEDGE_SEARCH_KEYWORDS) or ("fuente" in lowered and "sobre" in lowered):
        topic = _extract_topic_after(
            text, lowered, _KNOWLEDGE_SEARCH_TRIGGERS) or text
        return RoutedQuestion(intent=Intent.KNOWLEDGE_SEARCH, knowledgeQuery=topic)

    # Las búsquedas por nombre no se tratan como búsquedas por identificador.
    if name:
        if any(keyword in lowered for keyword in _ENERGY_KEYWORDS):
            return RoutedQuestion(intent=Intent.CONSULTATION_CALCULATION, patientName=name, wantsExplanation=wants_explanation)
        if "plan" in lowered:
            return RoutedQuestion(intent=Intent.PATIENT_PLANS, patientName=name, wantsExplanation=wants_explanation)
        if "consulta" in lowered:
            return RoutedQuestion(intent=Intent.PATIENT_CONSULTATIONS, patientName=name, wantsExplanation=wants_explanation)
        return RoutedQuestion(intent=Intent.PATIENT_BY_NAME, patientName=name, wantsExplanation=wants_explanation)

    # 6) Referencia genérica al plan abierto sin palabra clave específica.
    if plan_id:
        return RoutedQuestion(intent=Intent.PLAN_DETAIL, planIdA=plan_id, wantsExplanation=wants_explanation)

    return RoutedQuestion(intent=Intent.GENERAL_ASSISTANT, wantsExplanation=wants_explanation)
