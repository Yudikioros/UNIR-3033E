"""Pruebas puras del servicio de generación de borradores (Fase 4). Sin base de datos ni LLM real."""
import types
import unittest

from app.schemas.generation import DietPlanGenerationContext, GeneratedDietPlan
from app.services import diet_plan_generation as gen


def _context(**overrides):
    defaults = dict(
        age=28, sex='female', weightKg=68.0, heightM=1.65, activityLevel='moderate', goal='WEIGHT_LOSS',
        mealsPerDay=5, dailyBudget=None, foodPreferences=[], foodsToAvoid=[], allergiesOrIntolerances=[],
        notes=None, targetCalories=1685.89, proteinGrams=105.4, carbohydrateGrams=189.7,
        fatGrams=56.2, fiberGrams=23.6, waterLiters=2.38,
    )
    defaults.update(overrides)
    return DietPlanGenerationContext(**defaults)


def _plan(meals):
    return GeneratedDietPlan(summary='Borrador de prueba', meals=meals, recommendations=[])


def _meal(meal_type, foods):
    return {'mealType': meal_type, 'name': meal_type, 'foods': foods}


def _food(name, quantity=100.0, unit='g', calories=None, protein=None, carbohydrates=None, fat=None):
    return {'foodName': name, 'quantity': quantity, 'unit': unit, 'calories': calories,
            'protein': protein, 'carbohydrates': carbohydrates, 'fat': fat}


class PromptContentTests(unittest.TestCase):
    def test_prompt_incluye_requerimientos_calculados(self):
        context = _context()
        _system, user_prompt = gen.build_prompt(context, [], [], food_available=False, knowledge_available=False)
        self.assertIn('Target energy: 1685.89 kcal', user_prompt)
        self.assertIn('Protein: 105.4 g', user_prompt)
        self.assertIn('Carbohydrates: 189.7 g', user_prompt)
        self.assertIn('Fat: 56.2 g', user_prompt)
        self.assertIn('Fiber target: 23.6 g', user_prompt)
        self.assertIn('Water target: 2.38 L', user_prompt)

    def test_prompt_no_solicita_recalcular(self):
        context = _context()
        system_prompt, user_prompt = gen.build_prompt(context, [], [], food_available=False, knowledge_available=False)
        self.assertIn('No los recalcules', user_prompt)
        self.assertIn('Recalcular', system_prompt)
        self.assertNotIn('calcula las calorías', user_prompt.lower())
        self.assertNotIn('calcula los requerimientos', system_prompt.lower())

    def test_prompt_version_centralizada(self):
        self.assertEqual(gen.DIET_PLAN_PROMPT_VERSION, '1.0')

    def test_food_database_no_disponible_en_prompt(self):
        context = _context()
        _system, user_prompt = gen.build_prompt(context, [], [], food_available=False, knowledge_available=False)
        self.assertIn('no disponible todavía', user_prompt)
        self.assertNotIn('SMAE validado', user_prompt)

    def test_food_database_disponible_incluye_datos_verificados(self):
        context = _context(foodPreferences=['pollo'])
        food = types.SimpleNamespace(name='POLLO PECHUGA', energyKcal=165.0, proteinG=31.0, fatG=3.6, carbohydratesG=0.0)
        _system, user_prompt = gen.build_prompt(context, [food], [], food_available=True, knowledge_available=False)
        self.assertIn('POLLO PECHUGA', user_prompt)
        self.assertIn('Datos verificados de la base alimentaria', user_prompt)

    def test_rag_vacio_en_prompt(self):
        context = _context()
        _system, user_prompt = gen.build_prompt(context, [], [], food_available=False, knowledge_available=False)
        self.assertIn('No hay documentos de conocimiento clínico autorizados', user_prompt)
        self.assertIn('No cites ninguna fuente', user_prompt)

    def test_rag_con_fuente_en_prompt(self):
        context = _context()
        chunk = types.SimpleNamespace(documentName='Guía INSP', content='Contenido de referencia sobre fibra.')
        _system, user_prompt = gen.build_prompt(context, [], [chunk], food_available=False, knowledge_available=True)
        self.assertIn('Guía INSP', user_prompt)
        self.assertIn('Contenido de referencia sobre fibra', user_prompt)


class PrivacyTests(unittest.TestCase):
    """Sección 30: el contexto/prompt enviado al LLM nunca debe contener PII."""

    def test_contexto_no_admite_campos_de_identidad(self):
        forbidden = {'name', 'id', 'patientId', 'email', 'phone', 'birthDate'}
        self.assertTrue(forbidden.isdisjoint(DietPlanGenerationContext.model_fields.keys()))

    def test_build_context_no_filtra_pii_del_paciente(self):
        consultation = types.SimpleNamespace(
            id='11111111-1111-1111-1111-111111111111', patientId='22222222-2222-2222-2222-222222222222',
            ageAtConsultation=28, weightKg=68.0, heightM=1.65, sex='female', activityLevel='moderate',
            goal='WEIGHT_LOSS', mealsPerDay=5, dailyBudget=None, notes='Sin patologías declaradas.',
            patient=types.SimpleNamespace(name='María González', email='maria.gonzalez@example.com', phone='555-0100'),
        )
        projected = types.SimpleNamespace(
            foodPreferences='[]', foodsToAvoid='[]', allergiesOrIntolerances='[]',
            targetCalories=1685.89, proteinGrams=105.4, carbohydrateGrams=189.7,
            fatGrams=56.2, fiberGrams=23.6, waterLiters=2.38,
        )
        context = gen._build_context(consultation, projected)
        dumped = context.model_dump_json()
        system_prompt, user_prompt = gen.build_prompt(context, [], [], food_available=False, knowledge_available=False)
        payload = dumped + system_prompt + user_prompt
        for pii in ('María', 'González', consultation.id, consultation.patientId,
                    consultation.patient.email, consultation.patient.phone):
            self.assertNotIn(pii, payload)


class ValidationTests(unittest.TestCase):
    def test_meal_count_mismatch(self):
        context = _context(mealsPerDay=5)
        plan = _plan([_meal('Desayuno', [_food('Avena', calories=150)])])
        validations = gen.run_validations(context, plan, food_available=True, knowledge_available=True)
        codes = {v['code'] for v in validations}
        self.assertIn('MEAL_COUNT_MISMATCH', codes)
        mismatch = next(v for v in validations if v['code'] == 'MEAL_COUNT_MISMATCH')
        # Fase 5, sección 11: MEAL_COUNT_MISMATCH pasa a ser bloqueante para la aprobación.
        self.assertEqual(mismatch['severity'], 'ERROR')
        self.assertTrue(mismatch['isBlocking'])

    def test_restricted_food_found(self):
        context = _context(foodsToAvoid=['nueces'])
        plan = _plan([_meal('Colación', [_food('Ensalada con nueces', calories=200)])])
        validations = gen.run_validations(context, plan, food_available=True, knowledge_available=True)
        restricted = [v for v in validations if v['code'] == 'RESTRICTED_FOOD_FOUND']
        self.assertEqual(len(restricted), 1)
        self.assertEqual(restricted[0]['severity'], 'ERROR')
        self.assertTrue(restricted[0]['isBlocking'])

    def test_restricted_allergy_found(self):
        context = _context(allergiesOrIntolerances=['cacahuate'])
        plan = _plan([_meal('Colación', [_food('Crema de cacahuate', calories=200)])])
        validations = gen.run_validations(context, plan, food_available=True, knowledge_available=True)
        self.assertTrue(any(v['code'] == 'RESTRICTED_FOOD_FOUND' for v in validations))

    def test_energy_within_tolerance(self):
        context = _context(mealsPerDay=1, targetCalories=1000.0)
        plan = _plan([_meal('Comida', [_food('Alimento', calories=1030.0)])])  # 3% de desviación
        validations = gen.run_validations(context, plan, food_available=True, knowledge_available=True)
        codes = {v['code'] for v in validations}
        self.assertIn('ENERGY_WITHIN_TOLERANCE', codes)
        self.assertNotIn('ENERGY_OUT_OF_TOLERANCE', codes)

    def test_energy_out_of_tolerance(self):
        context = _context(mealsPerDay=1, targetCalories=1000.0)
        plan = _plan([_meal('Comida', [_food('Alimento', calories=1200.0)])])  # 20% de desviación
        validations = gen.run_validations(context, plan, food_available=True, knowledge_available=True)
        codes = {v['code'] for v in validations}
        self.assertIn('ENERGY_OUT_OF_TOLERANCE', codes)
        out_of_tolerance = next(v for v in validations if v['code'] == 'ENERGY_OUT_OF_TOLERANCE')
        # Fase 5, sección 11: ENERGY_OUT_OF_TOLERANCE pasa a ser bloqueante para la aprobación.
        self.assertEqual(out_of_tolerance['severity'], 'ERROR')
        self.assertTrue(out_of_tolerance['isBlocking'])

    def test_incomplete_nutrition_data_no_calcula_desviacion(self):
        context = _context(mealsPerDay=1)
        plan = _plan([_meal('Comida', [_food('Alimento sin calorías', calories=None)])])
        validations = gen.run_validations(context, plan, food_available=True, knowledge_available=True)
        codes = {v['code'] for v in validations}
        self.assertIn('INCOMPLETE_NUTRITION_DATA', codes)
        self.assertNotIn('ENERGY_WITHIN_TOLERANCE', codes)
        self.assertNotIn('ENERGY_OUT_OF_TOLERANCE', codes)
        incomplete = next(v for v in validations if v['code'] == 'INCOMPLETE_NUTRITION_DATA')
        # Fase 5, sección 11: INCOMPLETE_NUTRITION_DATA pasa a ser bloqueante para la aprobación.
        self.assertEqual(incomplete['severity'], 'ERROR')
        self.assertTrue(incomplete['isBlocking'])

    def test_food_database_unavailable_validation(self):
        context = _context(mealsPerDay=1)
        plan = _plan([_meal('Comida', [_food('Alimento', calories=1000.0)])])
        validations = gen.run_validations(context, plan, food_available=False, knowledge_available=True)
        self.assertTrue(any(v['code'] == 'FOOD_DATABASE_UNAVAILABLE' and not v['isBlocking'] for v in validations))

    def test_knowledge_base_unavailable_validation(self):
        context = _context(mealsPerDay=1)
        plan = _plan([_meal('Comida', [_food('Alimento', calories=1000.0)])])
        validations = gen.run_validations(context, plan, food_available=True, knowledge_available=False)
        self.assertTrue(any(v['code'] == 'KNOWLEDGE_BASE_UNAVAILABLE' and not v['isBlocking'] for v in validations))


class PlanMetricsTests(unittest.TestCase):
    def test_metrics_solo_si_todos_los_alimentos_tienen_el_dato(self):
        plan = _plan([_meal('Desayuno', [
            _food('A', calories=100, protein=10, carbohydrates=None, fat=5),
            _food('B', calories=200, protein=None, carbohydrates=20, fat=8),
        ])])
        metrics = gen.plan_metrics(plan)
        self.assertEqual(metrics.get('totalCalories'), 300.0)
        self.assertEqual(metrics.get('fatGrams'), 13.0)
        self.assertNotIn('proteinGrams', metrics)
        self.assertNotIn('carbohydrateGrams', metrics)

    def test_metrics_completos_cuando_todo_esta_presente(self):
        plan = _plan([_meal('Desayuno', [
            _food('A', calories=100, protein=10, carbohydrates=15, fat=5),
            _food('B', calories=200, protein=20, carbohydrates=25, fat=8),
        ])])
        metrics = gen.plan_metrics(plan)
        self.assertEqual(metrics, {'totalCalories': 300.0, 'proteinGrams': 30.0,
                                    'carbohydrateGrams': 40.0, 'fatGrams': 13.0})


if __name__ == '__main__':
    unittest.main()
