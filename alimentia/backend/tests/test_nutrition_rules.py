"""Pruebas de la matriz de trazabilidad de reglas nutricionales (Fase 6, Parte A).

No recalcula nada del motor de Fase 3: solo verifica que la matriz de
clasificación referencia las mismas constantes centralizadas, sin duplicarlas
ni inventar valores nuevos, y que ninguna regla se declara SOURCE_BACKED sin
una referencia real.
"""
import unittest

from app.services import calculator, nutrition_rules


class NutritionRulesetVersionTests(unittest.TestCase):
    def test_ruleset_version_centralizada_coincide_con_el_motor(self):
        self.assertEqual(nutrition_rules.NUTRITION_RULESET_VERSION, calculator.RULE_VERSION)
        self.assertEqual(nutrition_rules.NUTRITION_RULESET_VERSION, "1.0")

    def test_no_se_alteran_las_constantes_del_motor_de_calculo(self):
        """Auditoría metodológica de Fase 6: nunca cambia un resultado histórico."""
        self.assertEqual(calculator.ACTIVITY_FACTORS[calculator.ActivityLevel.SEDENTARY], 1.20)
        self.assertEqual(calculator.ACTIVITY_FACTORS[calculator.ActivityLevel.VERY_ACTIVE], 1.90)
        self.assertEqual(calculator.GOAL_ADJUSTMENTS_KCAL[calculator.NutritionGoal.LOSS], -500.0)
        self.assertEqual(calculator.FIBER_G_PER_1000_KCAL, 14.0)
        self.assertEqual(calculator.WATER_ML_PER_KG, 35.0)


class RuleMatrixTests(unittest.TestCase):
    def test_matriz_cubre_las_nueve_reglas_auditadas(self):
        rule_ids = {rule['ruleId'] for rule in nutrition_rules.NUTRITION_RULE_MATRIX}
        self.assertEqual(rule_ids, {
            'BMI', 'MIFFLIN_ST_JEOR_BMR', 'ACTIVITY_FACTOR', 'GOAL_ENERGY_ADJUSTMENT',
            'MACRO_DISTRIBUTION', 'FIBER_RULE', 'WATER_RULE', 'ENERGY_TOLERANCE', 'INPUT_RANGES',
        })

    def test_cada_regla_tiene_campos_obligatorios(self):
        required = {'ruleId', 'name', 'version', 'formula', 'unit', 'evidenceStatus',
                    'sourceReference', 'implementationStatus', 'notes'}
        for rule in nutrition_rules.NUTRITION_RULE_MATRIX:
            self.assertEqual(set(rule.keys()), required)
            self.assertEqual(rule['version'], nutrition_rules.NUTRITION_RULESET_VERSION)
            self.assertIn(rule['evidenceStatus'], {
                nutrition_rules.EvidenceStatus.SOURCE_BACKED, nutrition_rules.EvidenceStatus.MVP_ASSUMPTION,
                nutrition_rules.EvidenceStatus.PROFESSIONAL_CONFIGURABLE,
                nutrition_rules.EvidenceStatus.TECHNICAL_GUARD,
                nutrition_rules.EvidenceStatus.MVP_VALIDATION_THRESHOLD,
            })

    def test_source_backed_siempre_tiene_referencia_no_vacia(self):
        """Nunca se clasifica una regla como SOURCE_BACKED sin una referencia real."""
        for rule in nutrition_rules.NUTRITION_RULE_MATRIX:
            if rule['evidenceStatus'] == nutrition_rules.EvidenceStatus.SOURCE_BACKED:
                self.assertTrue(rule['sourceReference'] and rule['sourceReference'].strip())

    def test_mvp_assumption_nunca_tiene_referencia_bibliografica_inventada(self):
        """Sección 6/7/8: un valor MVP_ASSUMPTION nunca lleva una `sourceReference`
        (eso significaría afirmar una fuente que en realidad no está seleccionada)."""
        for rule in nutrition_rules.NUTRITION_RULE_MATRIX:
            if rule['evidenceStatus'] == nutrition_rules.EvidenceStatus.MVP_ASSUMPTION:
                self.assertIsNone(rule['sourceReference'])

    def test_factores_de_actividad_son_mvp_assumption(self):
        rule = next(r for r in nutrition_rules.NUTRITION_RULE_MATRIX if r['ruleId'] == 'ACTIVITY_FACTOR')
        self.assertEqual(rule['evidenceStatus'], nutrition_rules.EvidenceStatus.MVP_ASSUMPTION)
        self.assertIsNone(rule['sourceReference'])

    def test_tolerancia_energetica_es_umbral_de_validacion(self):
        rule = next(r for r in nutrition_rules.NUTRITION_RULE_MATRIX if r['ruleId'] == 'ENERGY_TOLERANCE')
        self.assertEqual(rule['evidenceStatus'], nutrition_rules.EvidenceStatus.MVP_VALIDATION_THRESHOLD)

    def test_rangos_de_captura_son_technical_guard(self):
        rule = next(r for r in nutrition_rules.NUTRITION_RULE_MATRIX if r['ruleId'] == 'INPUT_RANGES')
        self.assertEqual(rule['evidenceStatus'], nutrition_rules.EvidenceStatus.TECHNICAL_GUARD)

    def test_rule_matrix_devuelve_copia_no_la_lista_original(self):
        copy = nutrition_rules.rule_matrix()
        copy.clear()
        self.assertTrue(len(nutrition_rules.NUTRITION_RULE_MATRIX) > 0)


if __name__ == '__main__':
    unittest.main()
