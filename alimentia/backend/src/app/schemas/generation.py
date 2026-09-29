"""Contratos para generar y consultar borradores de planes.

El contexto enviado al modelo no contiene identificadores del paciente. La
salida se valida antes de usarse y persistirse.
"""
from datetime import datetime

from pydantic import ConfigDict, Field

from app.schemas.persistence import Contract, DietPlanRead


class DietPlanGenerationContext(Contract):
    model_config = ConfigDict(extra='forbid')

    age: int
    sex: str
    weightKg: float | None = None
    heightM: float | None = None
    activityLevel: str
    goal: str
    mealsPerDay: int
    dailyBudget: float | None = None
    foodPreferences: list[str] = Field(default_factory=list)
    foodsToAvoid: list[str] = Field(default_factory=list)
    allergiesOrIntolerances: list[str] = Field(default_factory=list)
    notes: str | None = None

    # El LLM recibe estos resultados como valores de referencia.
    targetCalories: float
    proteinGrams: float
    carbohydrateGrams: float
    fatGrams: float
    fiberGrams: float
    waterLiters: float


class GeneratedFood(Contract):
    model_config = ConfigDict(extra='forbid')
    foodName: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1)
    calories: float | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    carbohydrates: float | None = Field(default=None, ge=0)
    fat: float | None = Field(default=None, ge=0)
    notes: str | None = None


class GeneratedMeal(Contract):
    model_config = ConfigDict(extra='forbid')
    mealType: str = Field(min_length=1)
    name: str = Field(min_length=1)
    foods: list[GeneratedFood] = Field(min_length=1)


class GeneratedDietPlan(Contract):
    """Contrato de salida del LLM. No incluye fuentes bibliográficas libres ni SMAE:
    esos campos se completan después, desde datos verificados del backend."""
    model_config = ConfigDict(extra='forbid')
    summary: str
    meals: list[GeneratedMeal] = Field(min_length=1)
    recommendations: list[str] = Field(default_factory=list)


class PlanValidationRead(Contract):
    id: str
    severity: str
    code: str
    message: str
    source: str
    isBlocking: bool
    createdAt: datetime


class RetrievedSourceRead(Contract):
    id: str
    knowledgeSourceId: str
    documentName: str
    institution: str | None = None
    section: str | None = None
    retrievalScore: float | None = None


class DietPlanGenerationResponse(Contract):
    generationId: str
    dietPlanId: str | None = None
    version: int | None = None
    status: str
    plan: DietPlanRead | None = None
    validations: list[PlanValidationRead] = Field(default_factory=list)
    sources: list[RetrievedSourceRead] = Field(default_factory=list)
    foodDatabaseUsed: bool = False
    knowledgeBaseUsed: bool = False


class GenerationJobStarted(Contract):
    """Respuesta inmediata de los endpoints /generate-draft/start y
    /regenerate/start: solo el id para poder consultar el progreso real."""
    generationId: str


class GenerationStatusRead(Contract):
    """Progreso por etapas real (nunca simulado) de una generación en curso o
    terminada. `stage` usa los valores de GenerationStage
    (diet_plan_generation.py); nulo para generaciones registradas antes de
    esta funcionalidad."""
    generationId: str
    consultationId: str
    status: str
    stage: str | None = None
    startedAt: datetime
    completedAt: datetime | None = None
    errorMessage: str | None = None
    dietPlanId: str | None = None
