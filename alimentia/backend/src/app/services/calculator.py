"""
Calcula los requerimientos nutricionales de forma determinística.

El LLM no participa en estos cálculos. Las funciones heredadas se mantienen
para conservar compatibilidad con el endpoint antiguo.
"""
from datetime import datetime, timezone

from app.schemas.persistence import ActivityLevel, NutritionGoal, Sex

CALCULATION_METHOD = "MIFFLIN_ST_JEOR"
RULE_VERSION = "1.0"

# Factores de actividad asociados a los niveles del contrato.
ACTIVITY_FACTORS = {
    ActivityLevel.SEDENTARY: 1.20,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.90,
}

# Ajustes configurados para los objetivos del MVP; no son recomendaciones clínicas.
GOAL_ADJUSTMENTS_KCAL = {
    NutritionGoal.LOSS: -500.0,
    NutritionGoal.MAINTENANCE: 0.0,
    NutritionGoal.GAIN: 300.0,
}

# Distribución fija de macronutrientes del MVP.
MACRO_DISTRIBUTION_PERCENTAGE = {
    "protein": 25.0, "carbohydrate": 45.0, "fat": 30.0}
KCAL_PER_GRAM = {"protein": 4.0, "carbohydrate": 4.0, "fat": 9.0}

FIBER_G_PER_1000_KCAL = 14.0
WATER_ML_PER_KG = 35.0

# Rangos técnicos de captura; no son límites clínicos.
AGE_RANGE_YEARS = (18, 100)
WEIGHT_RANGE_KG = (20.0, 350.0)
HEIGHT_RANGE_M = (1.20, 2.30)


class NutritionCalculationError(ValueError):
    """Entrada técnicamente inválida o resultado fuera del límite de seguridad del MVP."""


def _in_range(value, bounds):
    low, high = bounds
    return value is not None and low <= value <= high


def validate_calculation_inputs(*, sex, age_at_consultation, weight_kg, height_m, activity_level, goal):
    """Valida los rangos técnicos de entrada, no criterios clínicos."""
    if sex not in set(Sex):
        raise NutritionCalculationError("Sexo no reconocido.")
    if activity_level not in set(ActivityLevel):
        raise NutritionCalculationError("Nivel de actividad no reconocido.")
    if goal not in set(NutritionGoal):
        raise NutritionCalculationError("Objetivo no reconocido.")
    age_min, age_max = AGE_RANGE_YEARS
    if not _in_range(age_at_consultation, AGE_RANGE_YEARS):
        raise NutritionCalculationError(
            f"Edad fuera del rango técnico admitido ({age_min}-{age_max} años).")
    weight_min, weight_max = WEIGHT_RANGE_KG
    if not _in_range(weight_kg, WEIGHT_RANGE_KG):
        raise NutritionCalculationError(
            f"Peso fuera del rango técnico admitido ({weight_min}-{weight_max} kg).")
    height_min, height_max = HEIGHT_RANGE_M
    if not _in_range(height_m, HEIGHT_RANGE_M):
        raise NutritionCalculationError(
            f"Talla fuera del rango técnico admitido ({height_min}-{height_max} m).")


def calculate_bmi(weight_kg: float, height_m: float) -> float:
    """Calcula el IMC como dato descriptivo; no se usa para tomar decisiones."""
    return weight_kg / (height_m ** 2)


def calculate_mifflin_st_jeor_bmr(weight_kg: float, height_m: float, age_yrs: int, sex: str) -> float:
    """Mifflin-St Jeor. La talla se convierte de metros a centímetros."""
    height_cm = height_m * 100.0
    base = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age_yrs)
    return base + 5.0 if sex == Sex.MALE else base - 161.0


def calculate_total_energy_expenditure(bmr: float, activity_level: str) -> float:
    """TDEE = BMR x factor de actividad."""
    return bmr * ACTIVITY_FACTORS[ActivityLevel(activity_level)]


def calculate_target_calories(tdee: float, goal: str, target_override: float | None = None) -> tuple[float, float]:
    """Energía objetivo = TDEE + ajuste por meta. Rechaza resultados <= 0 (sección 11)."""
    if target_override is not None:
        if target_override <= 0:
            raise NutritionCalculationError(
                "La energía objetivo personalizada debe ser mayor que cero.")
        return target_override, target_override - tdee
    adjustment = GOAL_ADJUSTMENTS_KCAL[NutritionGoal(goal)]
    target = tdee + adjustment
    if target <= 0:
        raise NutritionCalculationError(
            "El ajuste por objetivo produce una energía objetivo no válida (<= 0 kcal).")
    return target, adjustment


def calculate_macronutrients(target_calories: float) -> dict:
    """Convierte la distribución fija del MVP a gramos."""
    result = {}
    for name, percentage in MACRO_DISTRIBUTION_PERCENTAGE.items():
        calories = target_calories * (percentage / 100.0)
        result[name] = {
            "percentage": percentage,
            "calories": calories,
            "grams": calories / KCAL_PER_GRAM[name],
        }
    return result


def calculate_fiber_grams(target_calories: float) -> float:
    """14 g de fibra por cada 1000 kcal objetivo (sección 14)."""
    return target_calories / 1000.0 * FIBER_G_PER_1000_KCAL


def calculate_water_ml(weight_kg: float) -> float:
    """35 ml de agua por kg de peso corporal (sección 15)."""
    return weight_kg * WATER_ML_PER_KG


class NutritionCalculationService:
    """
    Orquesta el motor determinístico de cálculo nutricional.

    La misma entrada siempre produce la misma salida (salvo `calculatedAt`).
    No decide objetivos clínicos ni reemplaza el criterio del nutriólogo.
    """

    method = CALCULATION_METHOD
    rule_version = RULE_VERSION

    def calculate(self, *, sex, age_at_consultation, weight_kg, height_m, activity_level, goal,
                  target_calories_override=None, protein_grams_override=None,
                  carbohydrate_grams_override=None, fat_grams_override=None,
                  fiber_grams_override=None, water_liters_override=None) -> dict:
        validate_calculation_inputs(sex=sex, age_at_consultation=age_at_consultation, weight_kg=weight_kg,
                                    height_m=height_m, activity_level=activity_level, goal=goal)

        bmi = calculate_bmi(weight_kg, height_m)
        bmr = calculate_mifflin_st_jeor_bmr(
            weight_kg, height_m, age_at_consultation, sex)
        activity_factor = ACTIVITY_FACTORS[ActivityLevel(activity_level)]
        tdee = calculate_total_energy_expenditure(bmr, activity_level)
        target_calories, goal_adjustment = calculate_target_calories(
            tdee, goal, target_calories_override)
        macros = calculate_macronutrients(target_calories)
        protein_g = protein_grams_override if protein_grams_override is not None else macros[
            "protein"]["grams"]
        carbohydrate_g = carbohydrate_grams_override if carbohydrate_grams_override is not None else macros[
            "carbohydrate"]["grams"]
        fat_g = fat_grams_override if fat_grams_override is not None else macros[
            "fat"]["grams"]
        fiber_g = fiber_grams_override if fiber_grams_override is not None else calculate_fiber_grams(
            target_calories)
        water_l = water_liters_override if water_liters_override is not None else calculate_water_ml(
            weight_kg) / 1000.0

        metrics = {
            "bmi": round(bmi, 1),
            "basalMetabolicRate": round(bmr, 2),
            "totalEnergyExpenditure": round(tdee, 2),
            "targetCalories": round(target_calories, 2),
            "proteinGrams": round(protein_g, 1),
            "carbohydrateGrams": round(carbohydrate_g, 1),
            "fatGrams": round(fat_g, 1),
            "fiberGrams": round(fiber_g, 1),
            "waterLiters": round(water_l, 2),
        }

        details = {
            "bmrFormula": "Mifflin-St Jeor",
            "bmrInputs": {"weightKg": weight_kg, "heightCm": round(height_m * 100.0, 1),
                          "age": age_at_consultation, "sex": str(sex)},
            "activityLevel": str(activity_level),
            "activityFactor": activity_factor,
            "goal": str(goal),
            "goalAdjustmentKcal": goal_adjustment,
            "customOverrides": {
                "targetCalories": target_calories_override,
                "proteinGrams": protein_grams_override,
                "carbohydrateGrams": carbohydrate_grams_override,
                "fatGrams": fat_grams_override,
                "fiberGrams": fiber_grams_override,
                "waterLiters": water_liters_override,
            },
            "macroDistributionPercentage": {name: m["percentage"] for name, m in macros.items()},
            "fiberRule": f"{FIBER_G_PER_1000_KCAL:g} g / 1000 kcal",
            "waterRule": f"{WATER_ML_PER_KG:g} ml/kg",
            "waterMl": round(water_l * 1000.0, 1),
        }

        return {
            "metrics": metrics,
            "details": details,
            "calculationMethod": self.method,
            "calculationRuleVersion": self.rule_version,
            "calculatedAt": datetime.now(timezone.utc),
        }


nutrition_calculation_service = NutritionCalculationService()


# Compatibilidad con el endpoint legacy, que recibe texto libre en vez de enums.

def calculate_bmr(weight_kg: float, height_m: float, age_yrs: int, gender: str) -> float:
    """
    Calculates the Basal Metabolic Rate (BMR) using the Mifflin-St Jeor equation.
    Note: The formula requires height in centimeters.
    """
    height_cm = height_m * 100.0

    # Base formula calculation
    base_bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age_yrs)

    gender_normalized = gender.strip().lower()

    if gender_normalized == "male":
        return base_bmr + 5.0
    elif gender_normalized == "female":
        return base_bmr - 161.0
    else:
        raise ValueError("Gender must be 'male' or 'female'")


def calculate_tdee(bmr: float, activity_level: str) -> float:
    """
    Calculates Total Daily Energy Expenditure (TDEE) based on activity multipliers.
    """
    multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very active": 1.9
    }

    activity_normalized = activity_level.strip().lower()

    if activity_normalized not in multipliers:
        # Default to sedentary if input is unrecognized to err on the side of caution
        return bmr * 1.2

    return bmr * multipliers[activity_normalized]


def get_nutritional_baseline(weight: float, height: float, age: int, gender: str, activity_level: str) -> dict:
    """
    Orchestrates the calculations and returns a dictionary with the energy requirements.
    """
    bmr = calculate_bmr(weight, height, age, gender)
    tdee = calculate_tdee(bmr, activity_level)

    return {
        "bmr_kcal": round(bmr, 2),
        "tdee_kcal": round(tdee, 2)
    }
