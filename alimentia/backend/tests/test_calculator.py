"""Pruebas del motor de cálculo nutricional determinístico (Fase 3). Sin base de datos."""
import unittest

from app.services.calculator import (
    NutritionCalculationError,
    calculate_bmi,
    calculate_fiber_grams,
    calculate_macronutrients,
    calculate_mifflin_st_jeor_bmr,
    calculate_target_calories,
    calculate_total_energy_expenditure,
    calculate_water_ml,
    nutrition_calculation_service,
)


class MifflinStJeorTests(unittest.TestCase):
    def test_01_bmr_hombre(self):
        # 80 kg, 1.80 m, 30 años -> 10*80 + 6.25*180 - 5*30 + 5
        bmr = calculate_mifflin_st_jeor_bmr(80, 1.80, 30, "male")
        self.assertAlmostEqual(bmr, 800 + 1125 - 150 + 5, places=6)

    def test_02_bmr_mujer(self):
        # 68 kg, 1.65 m, 28 años -> 10*68 + 6.25*165 - 5*28 - 161
        bmr = calculate_mifflin_st_jeor_bmr(68, 1.65, 28, "female")
        self.assertAlmostEqual(bmr, 680 + 1031.25 - 140 - 161, places=6)


class BasicMetricsTests(unittest.TestCase):
    def test_03_bmi(self):
        self.assertAlmostEqual(calculate_bmi(68, 1.65), 68 / (1.65 ** 2), places=6)

    def test_04_actividad_sedentaria(self):
        self.assertAlmostEqual(calculate_total_energy_expenditure(1500, "sedentary"), 1500 * 1.20, places=6)

    def test_05_actividad_moderada(self):
        self.assertAlmostEqual(calculate_total_energy_expenditure(1500, "moderate"), 1500 * 1.55, places=6)


class TargetCaloriesTests(unittest.TestCase):
    def test_06_perdida_de_peso(self):
        target, adjustment = calculate_target_calories(2000, "WEIGHT_LOSS")
        self.assertEqual(adjustment, -500.0)
        self.assertAlmostEqual(target, 1500.0, places=6)

    def test_07_mantenimiento(self):
        target, adjustment = calculate_target_calories(2000, "MAINTENANCE")
        self.assertEqual(adjustment, 0.0)
        self.assertAlmostEqual(target, 2000.0, places=6)

    def test_08_incremento_de_peso(self):
        target, adjustment = calculate_target_calories(2000, "WEIGHT_GAIN")
        self.assertEqual(adjustment, 300.0)
        self.assertAlmostEqual(target, 2300.0, places=6)

    def test_target_calories_no_puede_ser_cero_o_negativo(self):
        with self.assertRaises(NutritionCalculationError):
            calculate_target_calories(400, "WEIGHT_LOSS")  # 400 - 500 = -100


class MacronutrientTests(unittest.TestCase):
    def test_09_proteina(self):
        macros = calculate_macronutrients(2000)
        self.assertAlmostEqual(macros["protein"]["grams"], (2000 * 0.25) / 4, places=6)

    def test_10_carbohidratos(self):
        macros = calculate_macronutrients(2000)
        self.assertAlmostEqual(macros["carbohydrate"]["grams"], (2000 * 0.45) / 4, places=6)

    def test_11_grasa(self):
        macros = calculate_macronutrients(2000)
        self.assertAlmostEqual(macros["fat"]["grams"], (2000 * 0.30) / 9, places=6)

    def test_macro_percentages_suman_100(self):
        macros = calculate_macronutrients(2000)
        self.assertEqual(sum(m["percentage"] for m in macros.values()), 100.0)


class FiberAndWaterTests(unittest.TestCase):
    def test_12_fibra(self):
        self.assertAlmostEqual(calculate_fiber_grams(2000), 2000 / 1000 * 14, places=6)

    def test_13_agua(self):
        self.assertAlmostEqual(calculate_water_ml(68), 68 * 35, places=6)


class InvalidInputTests(unittest.TestCase):
    def calc(self, **overrides):
        params = dict(sex="female", age_at_consultation=28, weight_kg=68, height_m=1.65,
            activity_level="moderate", goal="WEIGHT_LOSS")
        params.update(overrides)
        return nutrition_calculation_service.calculate(**params)

    def test_14_edad_invalida(self):
        with self.assertRaises(NutritionCalculationError):
            self.calc(age_at_consultation=17)
        with self.assertRaises(NutritionCalculationError):
            self.calc(age_at_consultation=101)

    def test_15_peso_invalido(self):
        with self.assertRaises(NutritionCalculationError):
            self.calc(weight_kg=10)
        with self.assertRaises(NutritionCalculationError):
            self.calc(weight_kg=400)

    def test_16_talla_invalida(self):
        with self.assertRaises(NutritionCalculationError):
            self.calc(height_m=1.0)
        with self.assertRaises(NutritionCalculationError):
            self.calc(height_m=2.5)

    def test_17_sexo_invalido(self):
        with self.assertRaises(NutritionCalculationError):
            self.calc(sex="other")

    def test_18_actividad_invalida(self):
        with self.assertRaises(NutritionCalculationError):
            self.calc(activity_level="extreme")

    def test_19_objetivo_invalido(self):
        with self.assertRaises(NutritionCalculationError):
            self.calc(goal="RECOMPOSITION")


class ReproducibilityTests(unittest.TestCase):
    def test_20_reproducibilidad_del_mismo_calculo(self):
        params = dict(sex="male", age_at_consultation=41, weight_kg=82, height_m=1.78,
            activity_level="active", goal="MAINTENANCE")
        first = nutrition_calculation_service.calculate(**params)
        second = nutrition_calculation_service.calculate(**params)
        self.assertEqual(first["metrics"], second["metrics"])
        self.assertEqual(first["details"], second["details"])
        self.assertEqual(first["calculationMethod"], second["calculationMethod"])
        self.assertEqual(first["calculationRuleVersion"], second["calculationRuleVersion"])


class MariaGonzalezDemoTests(unittest.TestCase):
    """Valida el motor con los datos exactos del caso de demostración (sección 26).

    Las cifras esperadas se calculan aquí con la fórmula en bruto -no llamando
    al servicio bajo prueba- para demostrar que el resultado se obtiene
    matemáticamente y no está hardcodeado.
    """

    def test_26_maria_gonzalez_demo(self):
        weight_kg, height_m, age, sex, activity, goal = 68.0, 1.65, 28, "female", "moderate", "WEIGHT_LOSS"

        expected_bmi = weight_kg / (height_m ** 2)
        expected_bmr = (10 * weight_kg) + (6.25 * (height_m * 100)) - (5 * age) - 161
        expected_tdee = expected_bmr * 1.55
        expected_target = expected_tdee - 500
        expected_protein_g = (expected_target * 0.25) / 4
        expected_carb_g = (expected_target * 0.45) / 4
        expected_fat_g = (expected_target * 0.30) / 9
        expected_fiber_g = expected_target / 1000 * 14
        expected_water_l = (weight_kg * 35) / 1000

        result = nutrition_calculation_service.calculate(sex=sex, age_at_consultation=age,
            weight_kg=weight_kg, height_m=height_m, activity_level=activity, goal=goal)
        metrics = result["metrics"]

        self.assertAlmostEqual(metrics["bmi"], round(expected_bmi, 1), places=6)
        self.assertAlmostEqual(metrics["basalMetabolicRate"], round(expected_bmr, 2), places=6)
        self.assertAlmostEqual(metrics["totalEnergyExpenditure"], round(expected_tdee, 2), places=6)
        self.assertAlmostEqual(metrics["targetCalories"], round(expected_target, 2), places=6)
        self.assertAlmostEqual(metrics["proteinGrams"], round(expected_protein_g, 1), places=6)
        self.assertAlmostEqual(metrics["carbohydrateGrams"], round(expected_carb_g, 1), places=6)
        self.assertAlmostEqual(metrics["fatGrams"], round(expected_fat_g, 1), places=6)
        self.assertAlmostEqual(metrics["fiberGrams"], round(expected_fiber_g, 1), places=6)
        self.assertAlmostEqual(metrics["waterLiters"], round(expected_water_l, 2), places=6)
        self.assertEqual(result["calculationMethod"], "MIFFLIN_ST_JEOR")
        self.assertEqual(result["calculationRuleVersion"], "1.0")
        # Un objetivo de pérdida de peso razonable para este perfil (sanity check, no regla clínica).
        self.assertGreater(metrics["targetCalories"], 0)
        self.assertLess(metrics["targetCalories"], expected_tdee)


if __name__ == '__main__':
    unittest.main()
