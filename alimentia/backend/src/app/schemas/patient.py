from pydantic import BaseModel, Field
from typing import List, Optional


class PatientIn(BaseModel):
    # Datos personales básicos.
    age: int = Field(..., gt=0, description="Patient age in years")
    gender: str = Field(..., description="Female or Male")
    weight: float = Field(..., gt=0, description="Weight in kilograms")
    height: float = Field(..., gt=0,
                          description="Height in meters (e.g., 1.70)")

    # Objetivo y estilo de vida.
    goal: str = Field(...,
                      description="E.g., Weight loss, Metabolic control, Hypertrophy")
    activity_level: str = Field(...,
                                description="Sedentary, Light, Moderate, Active, Very Active")

    # Antecedentes declarados para el contexto de generación.
    pathologies: Optional[List[str]] = Field(
        default=[], description="E.g., Diabetes, Hypertension, CKD")
    medications: Optional[List[str]] = Field(
        default=[], description="To identify drug-nutrient interactions")
    allergies_intolerances: Optional[List[str]] = Field(
        default=[], description="E.g., Lactose, Peanuts, Shellfish")

    # Preferencias y contexto.
    food_preferences: Optional[List[str]] = Field(
        default=[], description="Preferred or rejected foods")
    cultural_restrictions: Optional[List[str]] = Field(default=[])
    budget: Optional[str] = Field(
        default="Flexible", description="E.g., $100 - $150 MXN daily")
    regional_availability: Optional[str] = Field(
        default="Mexico", description="To adapt to SMAE equivalents")
