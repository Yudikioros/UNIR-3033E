"""Phase 1 contracts. Unknown legacy observations are allowed only in Read DTOs."""
from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Sex(StrEnum):
    FEMALE = "female"
    MALE = "male"


class ActivityLevel(StrEnum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very active"


class NutritionGoal(StrEnum):
    LOSS = "WEIGHT_LOSS"
    MAINTENANCE = "MAINTENANCE"
    GAIN = "WEIGHT_GAIN"


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    MODIFIED = "MODIFIED"
    REGENERATED = "REGENERATED"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Contract(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class PatientCreate(Contract):
    name: str = Field(min_length=1, max_length=200)
    sex: Sex
    birthDate: datetime | None = None
    age: int | None = Field(default=None, ge=0, le=130)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    defaultActivityLevel: ActivityLevel | None = None
    defaultGoal: NutritionGoal | None = None
    defaultMealsPerDay: int | None = Field(default=None, ge=1, le=12)
    defaultDailyBudget: float | None = Field(default=None, ge=0)
    foodPreferences: str | None = Field(default=None, max_length=4000)
    foodsToAvoid: str | None = Field(default=None, max_length=4000)
    allergiesOrIntolerances: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=8000)

    @model_validator(mode="after")
    def single_age_source(self):
        if self.birthDate is not None and self.age is not None:
            raise ValueError('Provide birthDate or a recorded age, not both')
        if self.birthDate is not None and self.birthDate.date() > datetime.now(timezone.utc).date():
            raise ValueError('La fecha de nacimiento no puede ser futura.')
        return self


class PatientUpdate(Contract):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sex: Sex | None = None
    birthDate: datetime | None = None
    age: int | None = Field(default=None, ge=0, le=130)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    defaultActivityLevel: ActivityLevel | None = None
    defaultGoal: NutritionGoal | None = None
    defaultMealsPerDay: int | None = Field(default=None, ge=1, le=12)
    defaultDailyBudget: float | None = Field(default=None, ge=0)
    foodPreferences: str | None = Field(default=None, max_length=4000)
    foodsToAvoid: str | None = Field(default=None, max_length=4000)
    allergiesOrIntolerances: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=8000)
    expectedUpdatedAt: datetime | None = None

    @model_validator(mode="after")
    def required_columns_not_null(self):
        if self.birthDate is not None and self.age is not None:
            raise ValueError('Provide birthDate or a recorded age, not both')
        if self.birthDate is not None and self.birthDate.date() > datetime.now(timezone.utc).date():
            raise ValueError('La fecha de nacimiento no puede ser futura.')
        for key in ("name", "sex"):
            if key in self.model_fields_set and getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null")
        return self


class PatientRead(PatientCreate):
    id: str
    createdAt: datetime
    updatedAt: datetime


class NutritionConsultationRead(Contract):
    id: str
    patientId: str
    consultationDate: datetime
    ageAtConsultation: int | None = None
    sex: str | None = None
    weightKg: float | None = None
    heightM: float | None = None
    activityLevel: str | None = None
    goal: str | None = None
    mealsPerDay: int | None = None
    dailyBudget: float | None = None
    budgetMin: float | None = None
    budgetMax: float | None = None
    foodPreferences: str | None = None
    foodsToAvoid: str | None = None
    allergiesOrIntolerances: str | None = None
    notes: str | None = None
    calculationMethod: str | None = None
    bmi: float | None = None
    basalMetabolicRate: float | None = None
    totalEnergyExpenditure: float | None = None
    targetCalories: float | None = None
    proteinGrams: float | None = None
    carbohydrateGrams: float | None = None
    fatGrams: float | None = None
    fiberGrams: float | None = None
    waterLiters: float | None = None
    calculationRuleVersion: str | None = None
    calculationDetails: str | None = None
    createdAt: datetime
    updatedAt: datetime


class NutritionConsultationCreate(Contract):
    patientId: str
    consultationDate: datetime | None = None
    ageAtConsultation: int = Field(ge=18, le=130)
    sex: Sex
    weightKg: float = Field(gt=0)
    heightM: float = Field(gt=0, le=3)
    activityLevel: ActivityLevel
    goal: NutritionGoal
    mealsPerDay: int = Field(ge=1, le=12)
    dailyBudget: float | None = Field(default=None, ge=0)
    budgetMin: float | None = Field(default=None, ge=0)
    budgetMax: float | None = Field(default=None, ge=0)
    foodPreferences: str | None = None
    foodsToAvoid: str | None = None
    allergiesOrIntolerances: str | None = None
    notes: str | None = None
    calculationMethod: str = "MIFFLIN_ST_JEOR"

    @model_validator(mode="after")
    def budget_range(self):
        if self.budgetMin is not None and self.budgetMax is not None and self.budgetMin > self.budgetMax:
            raise ValueError("budgetMin must not exceed budgetMax")
        return self


class DietPlanFoodCreate(Contract):
    foodName: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1)
    smaeEquivalent: str | None = None
    calories: float | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    carbohydrates: float | None = Field(default=None, ge=0)
    fat: float | None = Field(default=None, ge=0)
    notes: str | None = None


class DietPlanFoodRead(Contract):
    id: str
    foodName: str
    quantity: float | None = None
    unit: str | None = None
    smaeEquivalent: str | None = None
    calories: float | None = None
    protein: float | None = None
    carbohydrates: float | None = None
    fat: float | None = None
    notes: str | None = None
    legacyQuantity: str | None = None


class DietPlanMealRead(Contract):
    id: str
    mealType: str
    name: str
    sortOrder: int
    foods: list[DietPlanFoodRead] = Field(default_factory=list)


class DietPlanRead(Contract):
    id: str
    consultationId: str
    version: int
    status: PlanStatus
    totalCalories: float | None = None
    proteinGrams: float | None = None
    carbohydrateGrams: float | None = None
    fatGrams: float | None = None
    fiberGrams: float | None = None
    waterLiters: float | None = None
    approvedAt: datetime | None = None
    approvedBy: str | None = None
    rejectedAt: datetime | None = None
    rejectedBy: str | None = None
    rejectionReason: str | None = None
    generationId: str | None = None
    summary: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime
    meals: list[DietPlanMealRead] = Field(default_factory=list)
