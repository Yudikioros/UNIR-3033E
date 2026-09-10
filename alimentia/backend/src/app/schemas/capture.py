"""Capture contracts; domain enums come from phase 1, not frontend defaults."""
from datetime import datetime
from enum import StrEnum
from pydantic import Field, model_validator
from app.schemas.persistence import (
    Contract, Sex, ActivityLevel, NutritionGoal, NutritionConsultationRead,
    PatientRead, PlanStatus,
)


class ConsultationStatus(StrEnum):
    DRAFT = 'DRAFT'
    READY = 'READY'


class PlanSummary(Contract):
    id: str
    version: int
    status: PlanStatus


class PatientDetail(PatientRead):
    # Preserve unfamiliar historical vocabulary in reads; new writes use enums.
    defaultGoal: str | None = None
    defaultActivityLevel: str | None = None
    conditions: list[str] = Field(default_factory=list)
    currentAge: int | None = None
    latestConsultationDate: datetime | None = None
    latestPlan: PlanSummary | None = None
    isDemo: bool = False


class ConsultationCapture(Contract):
    consultationDate: datetime | None = None
    ageAtConsultation: int | None = Field(default=None, ge=0, le=130)
    sex: Sex | None = None
    weightKg: float | None = Field(default=None, gt=0)
    heightM: float | None = Field(default=None, gt=0, le=3)
    activityLevel: ActivityLevel | None = None
    goal: NutritionGoal | None = None
    mealsPerDay: int | None = Field(default=None, ge=1, le=12)
    dailyBudget: float | None = Field(default=None, ge=0)
    budgetMin: float | None = Field(default=None, ge=0)
    budgetMax: float | None = Field(default=None, ge=0)
    foodPreferences: str | None = Field(default=None, max_length=4000)
    foodsToAvoid: str | None = Field(default=None, max_length=4000)
    allergiesOrIntolerances: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=8000)
    requiresProfessionalReview: bool = False
    status: ConsultationStatus = ConsultationStatus.DRAFT

    @model_validator(mode='after')
    def valid_budget(self):
        if self.budgetMin is not None and self.budgetMax is not None and self.budgetMin > self.budgetMax:
            raise ValueError('El presupuesto mínimo no puede superar el máximo.')
        if self.dailyBudget is not None and (self.budgetMin is not None or self.budgetMax is not None):
            raise ValueError('Indica un presupuesto diario o un rango, no ambos.')
        return self


class ConsultationUpdate(ConsultationCapture):
    expectedUpdatedAt: datetime | None = None


class ConsultationDetail(NutritionConsultationRead):
    status: ConsultationStatus
    requiresProfessionalReview: bool
    isEditable: bool
    readinessIssues: list[str]
    scopeWarning: str | None
    plans: list[PlanSummary]
