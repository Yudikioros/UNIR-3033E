"""Pruebas puras del PlanValidationService (Fase 5). Sin base de datos ni LLM."""
import unittest

from app.services import plan_validation as pv


def _meal(name, foods, meal_type=None):
    return {"mealType": meal_type or name, "name": name, "foods": foods}


def _food(name, quantity=100.0, unit="g", calories=None, protein=None, carbohydrates=None, fat=None):
    return {"foodName": name, "quantity": quantity, "unit": unit, "calories": calories,
            "protein": protein, "carbohydrates": carbohydrates, "fat": fat}


class ValidateMealsTests(unittest.TestCase):
    def test_estructura_vacia_es_bloqueante(self):
        validations = pv.validate_meals([], meals_per_day=3, target_calories=2000, restricted_terms=[])
        self.assertEqual(len(validations), 1)
        self.assertEqual(validations[0]["code"], "INCOMPLETE_STRUCTURE")
        self.assertTrue(validations[0]["isBlocking"])

    def test_comida_sin_alimentos_es_bloqueante(self):
        meals = [_meal("Desayuno", [])]
        validations = pv.validate_meals(meals, meals_per_day=1, target_calories=2000, restricted_terms=[])
        codes = {v["code"] for v in validations}
        self.assertIn("INCOMPLETE_STRUCTURE", codes)
        entry = next(v for v in validations if v["code"] == "INCOMPLETE_STRUCTURE")
        self.assertTrue(entry["isBlocking"])

    def test_meal_count_mismatch_es_bloqueante(self):
        meals = [_meal("Desayuno", [_food("Avena", calories=150)])]
        validations = pv.validate_meals(meals, meals_per_day=5, target_calories=2000, restricted_terms=[])
        entry = next(v for v in validations if v["code"] == "MEAL_COUNT_MISMATCH")
        self.assertEqual(entry["severity"], "ERROR")
        self.assertTrue(entry["isBlocking"])

    def test_meal_count_correcto_no_genera_mismatch(self):
        meals = [_meal("Desayuno", [_food("Avena", calories=150)])]
        validations = pv.validate_meals(meals, meals_per_day=1, target_calories=150, restricted_terms=[])
        codes = {v["code"] for v in validations}
        self.assertNotIn("MEAL_COUNT_MISMATCH", codes)

    def test_restricted_food_es_bloqueante(self):
        meals = [_meal("Colación", [_food("Ensalada con nueces", calories=200)])]
        validations = pv.validate_meals(meals, meals_per_day=1, target_calories=200, restricted_terms=["nueces"])
        entry = next(v for v in validations if v["code"] == "RESTRICTED_FOOD_FOUND")
        self.assertEqual(entry["severity"], "ERROR")
        self.assertTrue(entry["isBlocking"])

    def test_multiples_alimentos_restringidos_generan_multiples_hallazgos(self):
        meals = [_meal("Comida", [_food("Nueces", calories=100), _food("Leche entera", calories=150)])]
        validations = pv.validate_meals(meals, meals_per_day=1, target_calories=250,
            restricted_terms=["nueces", "leche"])
        restricted = [v for v in validations if v["code"] == "RESTRICTED_FOOD_FOUND"]
        self.assertEqual(len(restricted), 2)

    def test_cantidad_no_positiva_es_bloqueante(self):
        meals = [_meal("Comida", [_food("Arroz", quantity=0, calories=100)])]
        validations = pv.validate_meals(meals, meals_per_day=1, target_calories=100, restricted_terms=[])
        entry = next(v for v in validations if v["code"] == "INVALID_QUANTITY")
        self.assertTrue(entry["isBlocking"])

    def test_unidad_ausente_es_bloqueante(self):
        meals = [_meal("Comida", [_food("Arroz", unit="", calories=100)])]
        validations = pv.validate_meals(meals, meals_per_day=1, target_calories=100, restricted_terms=[])
        entry = next(v for v in validations if v["code"] == "INVALID_QUANTITY")
        self.assertTrue(entry["isBlocking"])

    def test_energia_dentro_de_tolerancia(self):
        meals = [_meal("Comida", [_food("Alimento", calories=1030)])]
        validations = pv.validate_meals(meals, meals_per_day=1, target_calories=1000, restricted_terms=[])
        entry = next(v for v in validations if v["code"] == "ENERGY_WITHIN_TOLERANCE")
        self.assertEqual(entry["severity"], "INFO")
        self.assertFalse(entry["isBlocking"])

    def test_energia_fuera_de_tolerancia_es_bloqueante(self):
        meals = [_meal("Comida", [_food("Alimento", calories=1200)])]
        validations = pv.validate_meals(meals, meals_per_day=1, target_calories=1000, restricted_terms=[])
        entry = next(v for v in validations if v["code"] == "ENERGY_OUT_OF_TOLERANCE")
        self.assertEqual(entry["severity"], "ERROR")
        self.assertTrue(entry["isBlocking"])

    def test_desviacion_limite_5_porciento_es_valida(self):
        meals = [_meal("Comida", [_food("Alimento", calories=1050)])]  # exactamente 5%
        validations = pv.validate_meals(meals, meals_per_day=1, target_calories=1000, restricted_terms=[])
        codes = {v["code"] for v in validations}
        self.assertIn("ENERGY_WITHIN_TOLERANCE", codes)

    def test_datos_nutricionales_incompletos_es_bloqueante(self):
        meals = [_meal("Comida", [_food("Alimento", calories=None)])]
        validations = pv.validate_meals(meals, meals_per_day=1, target_calories=1000, restricted_terms=[])
        entry = next(v for v in validations if v["code"] == "INCOMPLETE_NUTRITION_DATA")
        self.assertEqual(entry["severity"], "ERROR")
        self.assertTrue(entry["isBlocking"])

    def test_plan_completo_y_correcto_no_tiene_bloqueantes(self):
        meals = [_meal("Comida", [_food("Alimento", calories=1000)])]
        validations = pv.validate_meals(meals, meals_per_day=1, target_calories=1000, restricted_terms=[])
        self.assertFalse(any(v["isBlocking"] for v in validations))


class PlanTotalsTests(unittest.TestCase):
    def test_totales_solo_si_todos_los_alimentos_tienen_el_dato(self):
        meals = [_meal("Comida", [
            _food("A", calories=100, protein=10, carbohydrates=None, fat=5),
            _food("B", calories=200, protein=None, carbohydrates=20, fat=8),
        ])]
        totals = pv.plan_totals(meals)
        self.assertEqual(totals.get("totalCalories"), 300.0)
        self.assertEqual(totals.get("fatGrams"), 13.0)
        self.assertNotIn("proteinGrams", totals)
        self.assertNotIn("carbohydrateGrams", totals)

    def test_totales_vacios_sin_alimentos(self):
        self.assertEqual(pv.plan_totals([]), {})


if __name__ == '__main__':
    unittest.main()
