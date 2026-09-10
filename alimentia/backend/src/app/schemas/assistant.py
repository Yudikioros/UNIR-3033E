"""
Contratos del asistente IA contextual de AlimentIA.

Principio (sección 3 del pedido): el asistente NO es la fuente de verdad. Los
DTOs de esta capa son deliberadamente minimizados (sección 19): nunca
exponen email/teléfono/domicilio/notas libres al LLM, solo lo necesario para
responder preguntas clínicas/administrativas sobre pacientes, consultas,
cálculos, planes y fuentes documentales.
"""
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.persistence import Contract


class ToolName(StrEnum):
    GET_PATIENT = "get_patient"
    SEARCH_PATIENTS = "search_patients"
    GET_PATIENT_CONSULTATIONS = "get_patient_consultations"
    GET_CONSULTATION = "get_consultation"
    GET_CONSULTATION_CALCULATION = "get_consultation_calculation"
    GET_PATIENT_PLANS = "get_patient_plans"
    GET_CONSULTATION_PLANS = "get_consultation_plans"
    GET_PLAN = "get_plan"
    GET_PLAN_VALIDATIONS = "get_plan_validations"
    GET_PLAN_SOURCES = "get_plan_sources"
    COMPARE_PLAN_VERSIONS = "compare_plan_versions"
    SEARCH_KNOWLEDGE = "search_knowledge"
    LIST_KNOWLEDGE_SOURCES = "list_knowledge_sources"
    COUNT_PLANS_BY_STATUS = "count_plans_by_status"
    LIST_PATIENTS_BY_PLAN_STATUS = "list_patients_by_plan_status"


# --- DTOs minimizados devueltos por las herramientas -----------------------

class AssistantPatientRef(Contract):
    id: str
    name: str


class AssistantPatientSummary(Contract):
    id: str
    name: str
    sex: str | None = None
    currentAge: int | None = None
    defaultGoal: str | None = None
    conditions: list[str] = Field(default_factory=list)


class AssistantConsultationSummary(Contract):
    id: str
    patientId: str
    consultationDate: datetime
    status: str
    goal: str | None = None
    activityLevel: str | None = None
    weightKg: float | None = None
    heightM: float | None = None
    targetCalories: float | None = None
    proteinGrams: float | None = None
    carbohydrateGrams: float | None = None
    fatGrams: float | None = None
    fiberGrams: float | None = None
    waterLiters: float | None = None
    calculationMethod: str | None = None
    calculationRuleVersion: str | None = None


class AssistantCalculationDetail(Contract):
    consultationId: str
    calculationMethod: str | None = None
    calculationRuleVersion: str | None = None
    recordedAt: datetime | None = None
    bmi: float | None = None
    basalMetabolicRate: float | None = None
    activityFactor: float | None = None
    totalEnergyExpenditure: float | None = None
    goalAdjustmentKcal: float | None = None
    targetCalories: float | None = None
    macroDistributionPercentage: dict | None = None
    proteinGrams: float | None = None
    carbohydrateGrams: float | None = None
    fatGrams: float | None = None
    fiberGrams: float | None = None
    waterLiters: float | None = None


class AssistantPlanSummary(Contract):
    id: str
    consultationId: str
    version: int
    status: str
    totalCalories: float | None = None
    createdAt: datetime
    approvedAt: datetime | None = None
    rejectedAt: datetime | None = None


class AssistantFood(Contract):
    foodName: str
    quantity: float | None = None
    unit: str | None = None
    calories: float | None = None
    protein: float | None = None
    carbohydrates: float | None = None
    fat: float | None = None
    smaeEquivalent: str | None = None


class AssistantMeal(Contract):
    mealType: str
    name: str
    foods: list[AssistantFood] = Field(default_factory=list)


class AssistantValidation(Contract):
    code: str
    severity: str
    message: str
    isBlocking: bool


class AssistantSourceRef(Contract):
    knowledgeSourceId: str
    documentName: str
    institution: str | None = None
    section: str | None = None


class AssistantPlanDetail(Contract):
    id: str
    consultationId: str
    version: int
    status: str
    isEditable: bool
    createdAt: datetime
    totalCalories: float | None = None
    targetCalories: float | None = None
    proteinGrams: float | None = None
    carbohydrateGrams: float | None = None
    fatGrams: float | None = None
    fiberGrams: float | None = None
    waterLiters: float | None = None
    blockingValidationCount: int = 0
    approvedAt: datetime | None = None
    approvedBy: str | None = None
    rejectedAt: datetime | None = None
    rejectedBy: str | None = None
    rejectionReason: str | None = None
    meals: list[AssistantMeal] = Field(default_factory=list)
    validations: list[AssistantValidation] = Field(default_factory=list)
    sources: list[AssistantSourceRef] = Field(default_factory=list)


class AssistantKnowledgeChunk(Contract):
    sourceId: str
    documentName: str
    institution: str | None = None
    version: str | None = None
    content: str


class AssistantKnowledgeSourceRef(Contract):
    id: str
    documentName: str
    institution: str | None = None
    version: str | None = None
    sourceType: str | None = None
    isActive: bool


class PlanVersionComparison(Contract):
    planA: AssistantPlanSummary
    planB: AssistantPlanSummary
    statusChanged: bool
    totalCaloriesDelta: float | None = None
    mealCountA: int
    mealCountB: int
    foodsAdded: list[str] = Field(default_factory=list)
    foodsRemoved: list[str] = Field(default_factory=list)
    quantityChanges: list[dict] = Field(default_factory=list)
    validationsA: list[AssistantValidation] = Field(default_factory=list)
    validationsB: list[AssistantValidation] = Field(default_factory=list)


class PlanStatusCount(Contract):
    status: str
    count: int


class PatientPlanStatusRef(Contract):
    patientId: str
    patientName: str
    planId: str
    version: int
    status: str


# --- Contrato de decisión del agente (sección 16: router validado con Pydantic) --

class AssistantDecision(Contract):
    """Salida estructurada de cada paso del agente (nunca SQL, nunca texto libre
    para invocar herramientas: ver sección 9)."""
    action: str = Field(description="'use_tool', 'answer' o 'ask_clarification'")
    tool: ToolName | None = None
    arguments: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    answer: str | None = None


# --- Contrato HTTP público ---------------------------------------------------

class AssistantNavigationContext(Contract):
    route: str | None = None
    patientId: str | None = None
    consultationId: str | None = None
    planId: str | None = None


class AssistantConversationTurn(Contract):
    role: str
    content: str


class AssistantChatRequest(Contract):
    message: str = Field(min_length=1, max_length=1000)
    context: AssistantNavigationContext = Field(default_factory=AssistantNavigationContext)
    conversation: list[AssistantConversationTurn] = Field(default_factory=list)


class AssistantSourceCitation(Contract):
    sourceId: str
    documentName: str
    institution: str | None = None


class AssistantResponseMetadata(Contract):
    model: str
    promptVersion: str
    executionTimeMs: int
    toolIterations: int
    # Corrección post-lanzamiento (router determinístico): permite demostrar
    # dónde se va el tiempo y si una pregunta realmente necesitó al LLM.
    routingTimeMs: int = 0
    toolExecutionTimeMs: int = 0
    llmExecutionTimeMs: int = 0
    responseMode: str = Field(default="deterministic", description="'deterministic' o 'llm'")


class AssistantExplanation(Contract):
    """Salida de la única llamada opcional al LLM para explicar hechos ya
    verificados (sección 17/7): nunca decide qué herramienta usar."""
    answer: str


class AssistantChatResponse(Contract):
    answer: str
    toolsUsed: list[str] = Field(default_factory=list)
    sources: list[AssistantSourceCitation] = Field(default_factory=list)
    structuredData: dict | None = None
    metadata: AssistantResponseMetadata
