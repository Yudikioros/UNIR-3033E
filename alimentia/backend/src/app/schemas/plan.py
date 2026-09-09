from pydantic import BaseModel, Field
from typing import List
from enum import Enum


class FoodItem(BaseModel):
    food: str
    quantity: str
    calories: float = Field(..., ge=0)
    protein: str
    carbs: str


class Meal(BaseModel):
    time: str
    items: List[FoodItem]
    instructions: str


class DietPlanDraft(BaseModel):
    meals: List[Meal]
    clinical_alerts: List[str] = Field(default=[])


class PlanStatusEnum(str, Enum):
    BORRADOR = "BORRADOR"
    PLAN_APROBADO = "PLAN APROBADO"
    MODIFICADO = "MODIFICADO"


class PlanUpdateStatus(BaseModel):
    status: PlanStatusEnum
