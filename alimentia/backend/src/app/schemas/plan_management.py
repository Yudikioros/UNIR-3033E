"""Contratos del ciclo de vida human-in-the-loop del plan (Fase 5).

Reutiliza `DietPlanFoodCreate` (Fase 1) para la edición manual: ya exige
cantidad positiva y unidad no vacía, igual que el contrato de generación.
"""
from datetime import datetime

from pydantic import ConfigDict, Field

from app.schemas.generation import PlanValidationRead, RetrievedSourceRead
from app.schemas.persistence import Contract, DietPlanFoodCreate, DietPlanRead


class DietPlanMealEdit(Contract):
    model_config = ConfigDict(extra='forbid')
    mealType: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    foods: list[DietPlanFoodCreate] = Field(min_length=1)


class DietPlanEditRequest(Contract):
    model_config = ConfigDict(extra='forbid')
    meals: list[DietPlanMealEdit] = Field(min_length=1)
    actor: str | None = Field(default=None, max_length=200)
    expectedUpdatedAt: datetime | None = None


class ApprovalRequest(Contract):
    model_config = ConfigDict(extra='forbid')
    actor: str | None = Field(default=None, max_length=200)


class RejectionRequest(Contract):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=2000)
    actor: str | None = Field(default=None, max_length=200)


class RegenerateRequest(Contract):
    model_config = ConfigDict(extra='forbid')
    instructions: str | None = Field(default=None, max_length=500)
    actor: str | None = Field(default=None, max_length=200)


class DietPlanDetail(DietPlanRead):
    """Sección 3 de Fase 5: plan + objetivos de la consulta + validaciones + fuentes + generación."""
    targetCalories: float | None = None
    targetProteinGrams: float | None = None
    targetCarbohydrateGrams: float | None = None
    targetFatGrams: float | None = None
    targetFiberGrams: float | None = None
    targetWaterLiters: float | None = None
    validations: list[PlanValidationRead] = Field(default_factory=list)
    sources: list[RetrievedSourceRead] = Field(default_factory=list)
    blockingValidationCount: int = 0
    isEditable: bool = False
    generatedAt: datetime | None = None
    modelProvider: str | None = None
    modelName: str | None = None
    promptVersion: str | None = None
    knowledgeBaseVersion: str | None = None
