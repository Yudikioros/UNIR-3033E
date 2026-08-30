from pydantic import BaseModel, Field
from typing import List, Optional

class PatientIn(BaseModel):
    # Basic data
    age: int = Field(..., gt=0, description="Patient age in years")
    gender: str = Field(..., description="Female or Male")
    weight: float = Field(..., gt=0, description="Weight in kilograms")
    height: float = Field(..., gt=0, description="Height in meters (e.g., 1.70)")
    
    # Goals and lifestyle
    goal: str = Field(..., description="E.g., Weight loss, Metabolic control, Hypertrophy")
    activity_level: str = Field(..., description="Sedentary, Light, Moderate, Active, Very Active")
    
    # Clinical data critical for RAG and LLM
    pathologies: Optional[List[str]] = Field(default=[], description="E.g., Diabetes, Hypertension, CKD")
    medications: Optional[List[str]] = Field(default=[], description="To identify drug-nutrient interactions")
    allergies_intolerances: Optional[List[str]] = Field(default=[], description="E.g., Lactose, Peanuts, Shellfish")
    
    # Preferences and context
    food_preferences: Optional[List[str]] = Field(default=[], description="Preferred or rejected foods")
    cultural_restrictions: Optional[List[str]] = Field(default=[])
    budget: Optional[str] = Field(default="Flexible", description="E.g., $100 - $150 MXN daily")
    regional_availability: Optional[str] = Field(default="Mexico", description="To adapt to SMAE equivalents")