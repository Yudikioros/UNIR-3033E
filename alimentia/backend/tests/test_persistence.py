import json
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import unittest

from prisma import Prisma
from prisma.errors import PrismaError
from pydantic import ValidationError
from app.schemas.persistence import PatientCreate, PatientUpdate, NutritionConsultationCreate, DietPlanRead
from app.repositories.legacy import list_patients, list_plans
from app.repositories.legacy import save_legacy_draft
from app.repositories.normalized import create_patient, create_consultation, plan_read, consultation_read
from app.schemas.patient import PatientIn
from app.schemas.plan import DietPlanDraft
from seed import seed

ROOT = Path(__file__).resolve().parents[1]


def apply_sql(database):
    with closing(sqlite3.connect(database)) as db:
        for file in sorted((ROOT/'migrations').glob('*/migration.sql')):
            db.executescript(file.read_text(encoding='utf-8-sig'))
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


class PersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'test.db'
        apply_sql(self.path)
        self.url = 'file:' + self.path.as_posix()
        self.db = Prisma(datasource={'url': self.url})
        await self.db.connect()

    async def asyncTearDown(self):
        await self.db.disconnect()
        self.temp.cleanup()

    async def patient(self):
        dto = PatientCreate(name='Paciente de prueba', age=28, sex='female')
        return await create_patient(self.db, dto)

    async def consultation(self):
        patient = await self.patient()
        dto = NutritionConsultationCreate(patientId=patient.id, ageAtConsultation=28,
            sex='female', weightKg=68, heightM=1.65, activityLevel='moderate',
            goal='WEIGHT_LOSS', mealsPerDay=5)
        return await create_consultation(self.db, dto)

    async def plan(self):
        consultation = await self.consultation()
        return await self.db.dietplan.create(data={'consultationId': consultation.id})

    async def test_01_patient_creation(self):
        patient = await self.patient()
        self.assertEqual(patient.sex, 'female')
        self.assertIsNotNone(patient.updatedAt)

    async def test_02_consultation_creation(self):
        consultation = await self.consultation()
        self.assertEqual(consultation.weightKg, 68)
        self.assertEqual(await self.db.calculationmetric.count(), 0)

    async def test_03_patient_consultation_relation(self):
        consultation = await self.consultation()
        patient = await self.db.patient.find_unique(where={'id': consultation.patientId}, include={'consultations': True})
        self.assertEqual(patient.consultations[0].id, consultation.id)

    async def test_04_plan_version_one(self):
        plan = await self.plan()
        self.assertEqual((plan.version, plan.status), (1, 'DRAFT'))
        self.assertIsNone(plan.approvedAt)

    async def test_05_second_version(self):
        first = await self.plan()
        second = await self.db.dietplan.create(data={'consultationId': first.consultationId, 'version': 2})
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(await self.db.dietplan.count(), 2)

    async def test_06_duplicate_version_rejected(self):
        first = await self.plan()
        with self.assertRaises(PrismaError):
            await self.db.dietplan.create(data={'consultationId': first.consultationId, 'version': 1})

    async def test_07_reconnect_preserves_data(self):
        plan = await self.plan()
        await self.db.disconnect()
        self.db = Prisma(datasource={'url': self.url})
        await self.db.connect()
        restored = await self.db.dietplan.find_unique(where={'id': plan.id}, include={'consultation': True})
        self.assertEqual(restored.consultation.weightKg, 68)

    async def test_08_meal_food_relations(self):
        plan = await self.plan()
        meal = await self.db.dietplanmeal.create(data={'dietPlanId': plan.id,
            'mealType': 'BREAKFAST', 'name': 'Desayuno', 'sortOrder': 0})
        await self.db.dietplanfood.create(data={'dietPlanMealId': meal.id, 'foodName': 'Alimento de prueba',
            'quantity': 40.0, 'unit': 'g', 'calories': 150.0, 'protein': 5.0})
        loaded = await self.db.dietplan.find_unique(where={'id': plan.id}, include={'meals': {'include': {'foods': True}}})
        dto = plan_read(loaded)
        self.assertEqual(dto.meals[0].foods[0].quantity, 40.0)

    async def test_09_generation_and_origin_relation(self):
        plan = await self.plan()
        generation = await self.db.aigeneration.create(data={'consultationId': plan.consultationId,
            'modelProvider': 'test', 'modelName': 'fixture', 'status': 'SUCCEEDED'})
        await self.db.generationplanlink.create(data={'generationId': generation.id, 'dietPlanId': plan.id, 'isOrigin': True})
        updated = await self.db.dietplan.find_unique(where={'id': plan.id}, include={'generationLinks': True})
        self.assertEqual(updated.generationLinks[0].generationId, generation.id)
        self.assertFalse(generation.retainPayloads)
        self.assertIsNone(generation.requestPayload)

    async def test_10_retrieved_source_relation(self):
        consultation = await self.consultation()
        generation = await self.db.aigeneration.create(data={'consultationId': consultation.id,
            'modelProvider': 'test', 'modelName': 'fixture', 'status': 'FAILED'})
        source = await self.db.knowledgesource.create(data={'documentName': 'Documento de prueba'})
        await self.db.retrievedsource.create(data={'generationId': generation.id,
            'knowledgeSourceId': source.id, 'content': 'Fragmento de prueba', 'retrievalScore': 0.8})
        loaded = await self.db.aigeneration.find_unique(where={'id': generation.id}, include={'retrievedSources': {'include': {'knowledgeSource': True}}})
        self.assertEqual(loaded.retrievedSources[0].knowledgeSource.id, source.id)

    async def test_11_seed_idempotent(self):
        await seed(self.db)
        await seed(self.db)
        self.assertEqual(await self.db.patient.count(), 1)
        self.assertEqual(await self.db.nutritionconsultation.count(), 1)
        self.assertEqual(await self.db.dietplan.count(), 0)
        patient = await self.db.patient.find_first()
        self.assertEqual(await self.db.patientcondition.count(), 0)

    async def test_12_status_and_severity_constraints(self):
        plan = await self.plan()
        with self.assertRaises(PrismaError):
            await self.db.dietplan.update(where={'id': plan.id}, data={'status': 'BORRADOR'})
        with self.assertRaises(PrismaError):
            await self.db.planvalidation.create(data={'dietPlanId': plan.id, 'severity': 'SUCCESS',
                'code': 'TEST', 'message': 'Test', 'source': 'Test'})

    async def test_13_validation_and_audit_records(self):
        plan = await self.plan()
        await self.db.planvalidation.create(data={'dietPlanId': plan.id, 'severity': 'WARNING',
            'code': 'TEST', 'message': 'Test', 'source': 'Test', 'isBlocking': False})
        await self.db.dietplanchangelog.create(data={'dietPlanId': plan.id,
            'changedBy': 'fixture-professional', 'changeType': 'TEST', 'field': 'notes',
            'previousValue': 'before', 'newValue': 'after'})
        loaded = await self.db.dietplan.find_unique(where={'id': plan.id}, include={'validations': True, 'changes': True})
        self.assertEqual(len(loaded.validations), 1)
        self.assertEqual(loaded.changes[0].changedBy, 'fixture-professional')

    async def test_14_payload_retention_default_blocks_capture(self):
        consultation = await self.consultation()
        with self.assertRaises(PrismaError):
            await self.db.aigeneration.create(data={'consultationId': consultation.id,
                'modelProvider': 'test', 'modelName': 'fixture', 'status': 'FAILED', 'requestPayload': '{}'})

    async def test_15_legacy_response_compatibility(self):
        await self.plan()
        patients = await list_patients(self.db)
        plans = await list_plans(self.db)
        self.assertEqual(patients[0]['gender'], 'female')
        self.assertEqual(plans[0]['status'], 'BORRADOR')

    async def test_16_foreign_keys_preserve_history(self):
        plan = await self.plan()
        consultation = await self.db.nutritionconsultation.find_unique(where={'id': plan.consultationId})
        with self.assertRaises(PrismaError):
            await self.db.patient.delete(where={'id': consultation.patientId})

    def test_17_contracts_reject_invalid_values(self):
        with self.assertRaises(ValidationError):
            PatientUpdate(name=None)
        with self.assertRaises(ValidationError):
            PatientCreate(name='Test', sex='invalid')

    async def test_18_cross_patient_plan_rejected(self):
        consultation = await self.consultation()
        plan = await self.db.dietplan.create(data={'consultationId': consultation.id}, include={'consultation': True})
        self.assertEqual(plan.consultation.patientId, consultation.patientId)
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertNotIn('patientId', {r[1] for r in conn.execute('PRAGMA table_info(DietPlan)')})

    async def test_19_cross_consultation_generation_rejected(self):
        plan = await self.plan()
        other = await self.consultation()
        generation = await self.db.aigeneration.create(data={'consultationId': other.id,
            'modelProvider': 'test', 'modelName': 'fixture', 'status': 'FAILED'})
        with self.assertRaises(PrismaError):
            await self.db.generationplanlink.create(data={'generationId': generation.id, 'dietPlanId': plan.id})

    async def test_20_existing_generation_persistence_adapter(self):
        patient = PatientIn(age=28, gender='female', weight=68, height=1.65,
            activity_level='moderate', goal='Pérdida de peso')
        payload = DietPlanDraft(meals=[], clinical_alerts=[])
        created = await save_legacy_draft(self.db, patient,
            {'bmr_kcal': 1400.0, 'tdee_kcal': 2000.0}, payload)
        plan = created.plans[0]
        self.assertEqual(plan.status, 'DRAFT')
        self.assertEqual(await self.db.nutritionconsultation.count(), 1)
        self.assertEqual(json.loads(plan.legacySnapshot.originalPlanJson), payload.model_dump())

    async def test_21_seed_preserves_existing_same_name_patient(self):
        legacy = await self.db.patient.create(data={'name': 'María González', 'sex': 'female',
            'age': 28, 'conditions': {'create': [{'description': 'Historical clinical data'}]}})
        await seed(self.db)
        await seed(self.db)
        retained = await self.db.patient.find_unique(where={'id': legacy.id}, include={'conditions': True})
        self.assertEqual(retained.conditions[0].description, 'Historical clinical data')
        self.assertEqual(await self.db.patient.count(), 2)

    async def test_22_nullable_legacy_patient_contract(self):
        from app.schemas.persistence import PatientRead
        created = await self.db.patient.create(data={'name': 'Age unknown', 'sex': 'female'})
        restored = PatientRead.model_validate(created)
        self.assertIsNone(restored.age)

    async def test_23_dietary_facts_are_individual_and_unique(self):
        dto = PatientCreate(name='Dietary fixture', sex='female',
            foodPreferences='["avena", "fruta", "avena"]', allergiesOrIntolerances='nueces')
        patient = await create_patient(self.db, dto)
        items = await self.db.patientdietaryitem.find_many(where={'patientId': patient.id})
        self.assertEqual({(i.kind, i.content) for i in items},
            {('PREFERENCE','avena'), ('PREFERENCE','fruta'), ('ALLERGY_OR_INTOLERANCE','nueces')})
        with self.assertRaises(PrismaError):
            await self.db.patientdietaryitem.create(data={'patientId': patient.id, 'kind': 'PREFERENCE', 'content': 'avena'})
        with self.assertRaises(PrismaError):
            await self.db.patientdietaryitem.create(data={'patientId': patient.id, 'kind': 'INVALID', 'content': 'x'})

    async def test_24_calculation_history_and_projection(self):
        consultation = await self.consultation()
        for value in (1800.0, 1900.0):
            await self.db.consultationcalculation.create(data={'consultationId': consultation.id,
                'calculationMethod': 'IMPORTED', 'metrics': {'create': [{'metricCode': 'targetCalories', 'value': value}]}})
        loaded = await self.db.nutritionconsultation.find_unique(where={'id': consultation.id},
            include={'dietaryItems': True, 'calculations': {'include': {'metrics': True}}})
        self.assertEqual(consultation_read(loaded).targetCalories, 1900.0)
        self.assertEqual(await self.db.calculationmetric.count(), 2)
        run = next(r for r in loaded.calculations if r.metrics)
        with self.assertRaises(PrismaError):
            await self.db.calculationmetric.create(data={'calculationId': run.id, 'metricCode': 'targetCalories', 'value': 2000.0})

    async def test_25_one_origin_and_consistent_consultation_updates(self):
        plan = await self.plan()
        generations = []
        for _ in range(2):
            generations.append(await self.db.aigeneration.create(data={'consultationId': plan.consultationId,
                'modelProvider': 'fixture', 'modelName': 'test', 'status': 'SUCCEEDED'}))
        await self.db.generationplanlink.create(data={'generationId': generations[0].id, 'dietPlanId': plan.id, 'isOrigin': True})
        with self.assertRaises(PrismaError):
            await self.db.generationplanlink.create(data={'generationId': generations[1].id, 'dietPlanId': plan.id, 'isOrigin': True})
        await self.db.generationplanlink.create(data={'generationId': generations[1].id, 'dietPlanId': plan.id})
        other = await self.consultation()
        with self.assertRaises(PrismaError):
            await self.db.aigeneration.update(where={'id': generations[0].id}, data={'consultationId': other.id})
        with self.assertRaises(PrismaError):
            await self.db.dietplan.update(where={'id': plan.id}, data={'consultationId': other.id})

    async def test_26_original_document_is_immutable(self):
        plan = await self.plan()
        consultation = await self.db.nutritionconsultation.find_unique(where={'id': plan.consultationId})
        await self.db.legacyplansnapshot.create(data={'dietPlanId': plan.id, 'originalPatientId': consultation.patientId, 'originalPlanJson': '{}'})
        with self.assertRaises(PrismaError):
            await self.db.legacyplansnapshot.update(where={'dietPlanId': plan.id}, data={'originalPlanJson': 'changed'})
        with self.assertRaises(PrismaError):
            await self.db.legacyplansnapshot.delete(where={'dietPlanId': plan.id})

    async def test_27_birth_date_and_current_age_cannot_conflict(self):
        from datetime import datetime, timezone
        birth = datetime(1998,1,1,tzinfo=timezone.utc)
        with self.assertRaises(ValidationError):
            PatientCreate(name='Test', sex='female', birthDate=birth, age=28)
        patient = await self.patient()
        with self.assertRaises(PrismaError):
            await self.db.patient.update(where={'id': patient.id}, data={'birthDate': birth})

    async def test_28_nutrient_and_origin_read_projection(self):
        plan = await self.plan()
        await self.db.plannutrientobservation.create(data={'dietPlanId': plan.id, 'metricCode': 'totalCalories', 'value': 1800.0})
        loaded = await self.db.dietplan.find_unique(where={'id': plan.id},
            include={'meals': {'include': {'foods': True}}, 'nutrientObservations': True, 'generationLinks': True})
        self.assertEqual(plan_read(loaded).totalCalories, 1800.0)
        with self.assertRaises(PrismaError):
            await self.db.plannutrientobservation.create(data={'dietPlanId': plan.id, 'metricCode': 'totalCalories', 'value': 1801.0})


class LegacyMigrationTests(unittest.TestCase):
    def test_third_normal_form_preserves_phase_one_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            with closing(sqlite3.connect(Path(tmp)/'phase1.db')) as db:
                migrations = sorted((ROOT/'migrations').glob('*/migration.sql'))
                for file in migrations[:2]:
                    db.executescript(file.read_text(encoding='utf-8-sig'))
                db.execute("INSERT INTO Patient(id,name,age,gender,goal,pathologies,foodPreferences) VALUES ('p','Original',28,'female','Pérdida de peso','Historical narrative',?)", ('["avena","fruta","avena"]',))
                db.execute("INSERT INTO NutritionConsultation(id,patientId,weightKg,heightM,bmi,totalEnergyExpenditure,calculationMethod,foodPreferences) VALUES ('c','p',68,1.65,24.98,1850,'ORIGINAL','[\"arroz\",\"fruta\"]')")
                payload = '{ "meals": [] }'
                db.execute("INSERT INTO DietPlan(id,patientId,consultationId,totalCalories,tdee_calculated,plan_json) VALUES ('d','p','c',1800,1850,?)", (payload,))
                db.execute("INSERT INTO AIGeneration(id,consultationId,dietPlanId,modelProvider,modelName,status) VALUES ('g','c','d','fixture','test','SUCCEEDED')")
                db.execute("UPDATE DietPlan SET generationId='g' WHERE id='d'")
                db.commit()
                db.executescript(migrations[2].read_text(encoding='utf-8-sig'))
                self.assertEqual(db.execute('SELECT originalPlanJson,originalTdee FROM LegacyPlanSnapshot').fetchone(), (payload,1850.0))
                self.assertEqual(db.execute('SELECT originalGoal,originalPathologies,originalPreferences FROM LegacyPatientSnapshot').fetchone(), ('Pérdida de peso','Historical narrative','["avena","fruta","avena"]'))
                self.assertEqual(db.execute('SELECT count(*) FROM PatientDietaryItem').fetchone()[0], 2)
                self.assertEqual(db.execute('SELECT count(*) FROM ConsultationDietaryItem').fetchone()[0], 2)
                self.assertEqual(dict(db.execute('SELECT metricCode,value FROM CalculationMetric')), {'bmi':24.98,'totalEnergyExpenditure':1850.0})
                self.assertEqual(db.execute('SELECT metricCode,value FROM PlanNutrientObservation').fetchone(), ('totalCalories',1800.0))
                self.assertEqual(db.execute('SELECT generationId,dietPlanId,isOrigin FROM GenerationPlanLink').fetchone(), ('g','d',1))
                self.assertEqual(db.execute('SELECT defaultGoal FROM Patient').fetchone()[0], 'WEIGHT_LOSS')
                for table, removed in {
                    'Patient': {'goal','pathologies','foodPreferences','foodsToAvoid','allergiesOrIntolerances'},
                    'DietPlan': {'patientId','generationId','plan_json','tdee_calculated','totalCalories'},
                    'AIGeneration': {'dietPlanId'},
                    'NutritionConsultation': {'bmi','targetCalories','foodPreferences'},
                }.items():
                    self.assertFalse(removed & {r[1] for r in db.execute(f'PRAGMA table_info({table})')})
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())

    def test_preserves_original_records_without_inventing_measurements(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'legacy.db'
            with closing(sqlite3.connect(path)) as db:
                db.executescript((ROOT/'migrations/202609050001_legacy_baseline/migration.sql').read_text(encoding='utf-8-sig'))
                db.execute("INSERT INTO Patient(id,name,age,gender,goal,pathologies) VALUES ('old-p','Original',28,'female','Pérdida de peso','Original pathology')")
                payload = json.dumps({'meals': [{'time': 'Desayuno', 'items': [{'food': 'Avena', 'quantity': '1 taza', 'calories': 150}]}]})
                db.execute("INSERT INTO DietPlan(id,patientId,tdee_calculated,plan_json,status) VALUES ('old-d','old-p',1850,?,'PLAN APROBADO')", (payload,))
                db.commit()
                db.executescript((ROOT/'migrations/202609050002_phase1_persistence/migration.sql').read_text(encoding='utf-8-sig'))
                self.assertEqual(db.execute('SELECT plan_json,status,legacyStatus,approvedBy FROM DietPlan').fetchone(), (payload,'APPROVED','PLAN APROBADO',None))
                self.assertEqual(db.execute('SELECT weightKg,heightM,ageAtConsultation FROM NutritionConsultation').fetchone(), (None,None,None))
                self.assertEqual(db.execute('SELECT foodName,quantity,unit,legacyQuantity,calories FROM DietPlanFood').fetchone(), ('Avena',1.0,'taza','1 taza',150.0))
                self.assertEqual(db.execute('SELECT pathologies FROM Patient').fetchone()[0], 'Original pathology')
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
