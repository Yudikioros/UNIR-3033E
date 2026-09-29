import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi import FastAPI
from prisma import Prisma
from app.routes.capture import router
from test_persistence import apply_sql


class CaptureHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'capture.db'
        apply_sql(self.path)
        self.db = Prisma(datasource={'url': 'file:' + self.path.as_posix()})
        await self.db.connect()
        self.app = FastAPI()
        self.app.state.db = self.db
        self.app.include_router(router)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test/api/v1/')

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.db.disconnect()
        self.temp.cleanup()

    async def patient(self, **changes):
        response = await self.client.post('patients', json={'name': 'Test patient', 'sex': 'female', 'age': 28, **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def consultation(self, patient=None, **changes):
        patient = patient or await self.patient()
        response = await self.client.post(f"patients/{patient['id']}/consultations", json=changes)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def test_patient_create_list_get_and_real_uuid(self):
        patient = await self.patient()
        self.assertEqual((await self.client.get('patients')).json()[0]['id'], patient['id'])
        self.assertEqual((await self.client.get('patients/'+patient['id'])).json()['name'], patient['name'])
        self.assertEqual((await self.client.get('patients/1')).status_code, 422)
        self.assertEqual((await self.client.get('patients/'+str(uuid4()))).status_code, 404)

    async def test_patient_patch_and_dietary_relations(self):
        patient = await self.patient(foodPreferences='["avena"]', foodsToAvoid='["nueces"]')
        response = await self.client.patch('patients/'+patient['id'], json={'name': 'Updated',
            'foodPreferences': '["arroz","fruta"]', 'expectedUpdatedAt': patient['updatedAt']})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['name'], 'Updated')
        self.assertEqual(await self.db.patientdietaryitem.count(), 3)
        self.assertIn('nueces', response.json()['foodsToAvoid'])
        stale = await self.client.patch('patients/'+patient['id'], json={'name': 'Lost update', 'expectedUpdatedAt': patient['updatedAt']})
        self.assertEqual(stale.status_code, 409)

    async def test_idempotent_patient_creation_and_key_conflict(self):
        headers = {'Idempotency-Key': str(uuid4())}
        payload = {'name': 'Retry', 'sex': 'female'}
        first = await self.client.post('patients', json=payload, headers=headers)
        second = await self.client.post('patients', json=payload, headers=headers)
        self.assertEqual(first.json()['id'], second.json()['id'])
        self.assertEqual(await self.db.patient.count(), 1)
        conflict = await self.client.post('patients', json={**payload, 'name': 'Other'}, headers=headers)
        self.assertEqual(conflict.status_code, 409)

    async def test_duplicate_identified_patient_not_created(self):
        payload = {'name': 'Same person', 'sex': 'female', 'birthDate': '1998-01-01T00:00:00Z'}
        self.assertEqual((await self.client.post('patients', json=payload)).status_code, 201)
        self.assertEqual((await self.client.post('patients', json=payload)).status_code, 409)
        self.assertEqual(await self.db.patient.count(), 1)

    async def test_invalid_patient_fields(self):
        for changes in [{'name': '   '}, {'sex': 'unknown'}, {'age': -1}, {'defaultDailyBudget': -1},
            {'defaultMealsPerDay': 0}, {'birthDate': '2999-01-01T00:00:00Z'}, {'notes': 'x'*8001}, {'name': 'x'*201}]:
            response = await self.client.post('patients', json={'name': 'Valid', 'sex': 'female', **changes})
            self.assertEqual(response.status_code, 422, response.text)

    async def test_patient_age_mode_change_is_coherent(self):
        patient = await self.patient()
        url = 'patients/'+patient['id']
        self.assertEqual((await self.client.patch(url, json={'birthDate': '1998-01-01T00:00:00Z'})).status_code, 422)
        self.assertEqual((await self.client.patch(url, json={'birthDate': '1998-01-01T00:00:00Z', 'age': None})).status_code, 200)

    async def test_consultation_defaults_relationship_and_no_new_patient(self):
        patient = await self.patient(defaultGoal='WEIGHT_LOSS', defaultMealsPerDay=5, foodPreferences='["avena"]')
        consultation = await self.consultation(patient)
        self.assertEqual(consultation['patientId'], patient['id'])
        self.assertEqual(consultation['goal'], patient['defaultGoal'])
        self.assertEqual(consultation['status'], 'DRAFT')
        self.assertIsNone(consultation['weightKg'])
        self.assertTrue(consultation['isEditable'])
        self.assertEqual(await self.db.patient.count(), 1)
        history = (await self.client.get(f"patients/{patient['id']}/consultations")).json()
        self.assertEqual(history[0]['id'], consultation['id'])
        self.assertEqual((await self.client.get('consultations/'+consultation['id'])).json()['id'], consultation['id'])

    async def test_consultation_retry(self):
        patient = await self.patient()
        url = f"patients/{patient['id']}/consultations"
        headers = {'Idempotency-Key': str(uuid4())}
        first = await self.client.post(url, json={}, headers=headers)
        second = await self.client.post(url, json={}, headers=headers)
        self.assertEqual(first.json()['id'], second.json()['id'])
        self.assertEqual(await self.db.nutritionconsultation.count(), 1)

    async def test_consultation_update_and_ready_lock(self):
        consultation = await self.consultation()
        url = 'consultations/'+consultation['id']
        response = await self.client.patch(url, json={'weightKg': 68, 'heightM': 1.65,
            'activityLevel': 'moderate', 'goal': 'WEIGHT_LOSS', 'mealsPerDay': 5,
            'expectedUpdatedAt': consultation['updatedAt']})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['readinessIssues'], [])
        ready = await self.client.patch(url, json={'status': 'READY'})
        self.assertEqual(ready.status_code, 200, ready.text)
        self.assertFalse(ready.json()['isEditable'])
        self.assertEqual((await self.client.patch(url, json={'weightKg': 69})).status_code, 409)
        self.assertEqual(await self.db.calculationmetric.count(), 0)
        self.assertEqual(await self.db.dietplan.count(), 0)

    async def test_readiness_incomplete_minor_and_scope(self):
        consultation = await self.consultation()
        url = 'consultations/'+consultation['id']
        self.assertEqual((await self.client.patch(url, json={'status': 'READY'})).status_code, 422)
        complete = {'ageAtConsultation': 17, 'weightKg': 68, 'heightM': 1.65, 'activityLevel': 'moderate', 'goal': 'WEIGHT_LOSS', 'mealsPerDay': 5, 'status': 'READY'}
        self.assertEqual((await self.client.patch(url, json=complete)).status_code, 422)
        response = await self.client.patch(url, json={**complete, 'ageAtConsultation': 28, 'requiresProfessionalReview': True})
        self.assertEqual(response.status_code, 422)
        self.assertIn('revisión profesional', response.json()['message'])

    async def test_invalid_consultation_and_missing_parent(self):
        missing = str(uuid4())
        self.assertEqual((await self.client.post(f'patients/{missing}/consultations', json={})).status_code, 404)
        self.assertEqual((await self.client.get('consultations/'+missing)).status_code, 404)
        consultation = await self.consultation()
        for payload in [{'heightM': 0}, {'weightKg': -1}, {'budgetMin': 160, 'budgetMax': 120}, {'patientId': missing}, {'status': 'APPROVED'}]:
            self.assertEqual((await self.client.patch('consultations/'+consultation['id'], json=payload)).status_code, 422)

    async def test_history_is_not_changed_by_patient_edit_and_reconnect(self):
        patient = await self.patient(defaultGoal='WEIGHT_LOSS')
        consultation = await self.consultation(patient, weightKg=68)
        await self.client.patch('patients/'+patient['id'], json={'defaultGoal': 'MAINTENANCE'})
        await self.db.disconnect()
        self.db = Prisma(datasource={'url': 'file:' + self.path.as_posix()})
        await self.db.connect()
        self.app.state.db = self.db
        restored = (await self.client.get('consultations/'+consultation['id'])).json()
        self.assertEqual(restored['weightKg'], 68)
        self.assertEqual(restored['goal'], 'WEIGHT_LOSS')

    async def test_existing_plan_locks_draft_consultation(self):
        consultation = await self.consultation()
        await self.db.dietplan.create(data={'consultationId': consultation['id']})
        url = 'consultations/'+consultation['id']
        self.assertFalse((await self.client.get(url)).json()['isEditable'])
        self.assertEqual((await self.client.patch(url, json={'weightKg': 70})).status_code, 409)

    async def test_conditions_are_not_copied_but_scope_warning_is_visible(self):
        patient = await self.patient()
        await self.db.patientcondition.create(data={'patientId': patient['id'], 'description': 'Recorded condition'})
        consultation = await self.consultation(patient)
        self.assertIsNone(consultation['notes'])
        self.assertIn('revisión profesional', consultation['scopeWarning'])
