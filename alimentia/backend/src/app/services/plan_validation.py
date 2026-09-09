"""
Motor de validaciones deterministas del plan (Fase 4/5): PlanValidationService.

Única fuente de verdad de severidad/bloqueo del plan dietético, usada tanto
en la generación con LLM (Fase 4) como en la revalidación automática tras
una edición manual (Fase 5). Nunca usa el LLM para decidir si el plan
cumple: todo aquí es aritmética y comparación de cadenas sobre datos ya
persistidos o a punto de persistirse.

Los códigos y su bloqueo (sección 11 de Fase 5):

    RESTRICTED_FOOD_FOUND     ERROR    bloqueante
    MEAL_COUNT_MISMATCH       ERROR    bloqueante
    INCOMPLETE_NUTRITION_DATA ERROR    bloqueante
    INVALID_QUANTITY          ERROR    bloqueante
    INCOMPLETE_STRUCTURE      ERROR    bloqueante
    ENERGY_OUT_OF_TOLERANCE   ERROR    bloqueante
    ENERGY_WITHIN_TOLERANCE   INFO     no bloqueante
    FOOD_DATABASE_UNAVAILABLE    WARNING  no bloqueante (se agrega en services.diet_plan_generation)
    KNOWLEDGE_BASE_UNAVAILABLE   WARNING  no bloqueante (se agrega en services.diet_plan_generation)
"""
from typing import Optional

ENERGY_TOLERANCE_PERCENT = 5.0
VALIDATION_SOURCE = "plan_validation"


def validation(severity: str, code: str, message: str, blocking: bool) -> dict:
    return {"severity": severity, "code": code, "message": message, "source": VALIDATION_SOURCE, "isBlocking": blocking}


def validate_meals(meals: list[dict], *, meals_per_day: Optional[int], target_calories: Optional[float],
                    restricted_terms: list[str]) -> list[dict]:
    """`meals`: lista de dicts {mealType, name, foods: [{foodName, quantity, unit, calories, protein, carbohydrates, fat}]}.

    Nunca lanza excepciones: una estructura vacía o incompleta produce
    validaciones bloqueantes, no un error de programación.
    """
    validations = []

    if not meals:
        validations.append(validation("ERROR", "INCOMPLETE_STRUCTURE", "El plan no contiene ninguna comida.", True))
        return validations

    if meals_per_day and len(meals) != meals_per_day:
        validations.append(validation("ERROR", "MEAL_COUNT_MISMATCH",
            f"El plan tiene {len(meals)} comida(s); se esperaban {meals_per_day}.", True))

    all_foods = []
    for meal in meals:
        foods = meal.get("foods") or []
        if not foods:
            validations.append(validation("ERROR", "INCOMPLETE_STRUCTURE",
                f"La comida '{meal.get('name') or meal.get('mealType') or '?'}' no tiene alimentos.", True))
            continue
        all_foods.extend(foods)

    restricted = [term.casefold() for term in restricted_terms if term and term.strip()]
    for food in all_foods:
        name = (food.get("foodName") or "").casefold()
        if name and any(term in name for term in restricted):
            validations.append(validation("ERROR", "RESTRICTED_FOOD_FOUND",
                f"'{food.get('foodName')}' coincide con una restricción o alergia declarada.", True))

    invalid_quantity = [food for food in all_foods
        if food.get("quantity") is None or food.get("quantity", 0) <= 0 or not (food.get("unit") or "").strip()]
    if invalid_quantity:
        validations.append(validation("ERROR", "INVALID_QUANTITY",
            f"{len(invalid_quantity)} alimento(s) tienen cantidad no positiva o sin unidad.", True))

    if all_foods and all(food.get("calories") is not None for food in all_foods):
        plan_calories = sum(food["calories"] for food in all_foods)
        if target_calories:
            deviation = (plan_calories - target_calories) / target_calories * 100
            if abs(deviation) <= ENERGY_TOLERANCE_PERCENT:
                validations.append(validation("INFO", "ENERGY_WITHIN_TOLERANCE",
                    f"Calorías del plan ({plan_calories:.0f} kcal) dentro de ±{ENERGY_TOLERANCE_PERCENT:.0f}% "
                    f"del objetivo ({target_calories:.0f} kcal).", False))
            else:
                validations.append(validation("ERROR", "ENERGY_OUT_OF_TOLERANCE",
                    f"Calorías del plan ({plan_calories:.0f} kcal) se desvían {deviation:.1f}% "
                    f"del objetivo ({target_calories:.0f} kcal).", True))
    elif all_foods:
        validations.append(validation("ERROR", "INCOMPLETE_NUTRITION_DATA",
            "No todos los alimentos incluyen calorías; no fue posible validar la desviación energética.", True))

    return validations


def plan_totals(meals: list[dict]) -> dict:
    """Totales derivables del plan, solo si TODOS los alimentos traen ese dato (nunca se asume)."""
    foods = [food for meal in meals for food in (meal.get("foods") or [])]
    totals = {}
    for metric_code, field in (("totalCalories", "calories"), ("proteinGrams", "protein"),
                                ("carbohydrateGrams", "carbohydrates"), ("fatGrams", "fat")):
        if foods and all(food.get(field) is not None for food in foods):
            totals[metric_code] = round(sum(food[field] for food in foods), 1)
    return totals
