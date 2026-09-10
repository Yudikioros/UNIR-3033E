"""Patient and consultation capture; all writes use the normalized relations."""
import hashlib
import json
from datetime import datetime, timezone
from pydantic import ValidationError
from app.repositories.normalized import DIETARY_FIELDS, dietary_create, dietary_values, dietary_projection, consultation_read
from app.schemas.persistence import Sex, ActivityLevel, NutritionGoal
from app.schemas.capture import PatientDetail, ConsultationCapture, ConsultationDetail
from app.services.calculator import nutrition_calculation_service, NutritionCalculationError

PATIENT_INCLUDE = {'dietaryItems': True, 'conditions': True,
    'consultations': {'include': {'plans': True}}}
CONSULTATION_INCLUDE = {'dietaryItems': True, 'plans': True, 'generations': True,
    'patient': {'include': {'conditions': True}}, 'calculations': {'include': {'metrics': True}}}
SCOPE_WARNING = 'Este caso puede encontrarse fuera del alcance del MVP y requiere revisión profesional antes de continuar.'
GOAL_ALIASES = {
    'Pérdida de peso': 'WEIGHT_LOSS', 'Mantenimiento': 'MAINTENANCE',
    'Ganancia muscular': 'WEIGHT_GAIN', 'Ganancia de peso': 'WEIGHT_GAIN', 'Incremento de peso': 'WEIGHT_GAIN',
}


class CaptureError(Exception):
    def __init__(self, status, message, existing_id=None, extra=None):
        super().__init__(message)
        self.status, self.message, self.existing_id = status, message, existing_id
        self.extra = extra or {}


def now():
    return datetime.now(timezone.utc)


def current_age(patient, at=None):
    if not patient.birthDate:
        return patient.age
    today = (at or now()).date()
    birth = patient.birthDate.date()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def patient_projection(patient):
    data = {k: v for k, v in patient.model_dump().items() if k in PatientDetail.model_fields}
    data.update(dietary_projection(patient.dietaryItems))
    data['defaultGoal'] = GOAL_ALIASES.get(patient.defaultGoal, patient.defaultGoal)
    data['conditions'] = [c.description for c in patient.conditions or []]
    data['currentAge'] = current_age(patient)
    data['isDemo'] = patient.demoKey is not None
    consultations = patient.consultations or []
    data['latestConsultationDate'] = max((c.consultationDate for c in consultations), default=None)
    plans = [p for c in consultations for p in c.plans or []]
    latest = max(plans, key=lambda p: p.createdAt, default=None)
    data['latestPlan'] = {'id': latest.id, 'version': latest.version, 'status': latest.status} if latest else None
    return PatientDetail.model_validate(data)


def editable(consultation):
    return consultation.status == 'DRAFT' and not consultation.plans and not consultation.generations and not any(c.metrics for c in consultation.calculations or [])


def readiness(data, patient):
    issues = []
    # Minimum age is the explicitly agreed MVP boundary, not a clinical calculation.
    if data.get('ageAtConsultation') is None or data['ageAtConsultation'] < 18:
        issues.append('La consulta requiere una edad registrada de al menos 18 años.')
    for field, label in [('weightKg', 'peso'), ('heightM', 'talla'), ('mealsPerDay', 'número de comidas')]:
        if data.get(field) is None or data[field] <= 0:
            issues.append(f'Completa el {label} de la consulta.')
    for field, values, label in [('sex', Sex, 'sexo'), ('activityLevel', ActivityLevel, 'nivel de actividad'), ('goal', NutritionGoal, 'objetivo')]:
        if data.get(field) not in set(values):
            issues.append(f'Define un {label} válido.')
    warning = SCOPE_WARNING if data.get('requiresProfessionalReview') or patient.conditions else None
    if warning:
        issues.append(warning)
    return issues, warning


def consultation_projection(consultation):
    data = consultation_read(consultation).model_dump()
    data['goal'] = GOAL_ALIASES.get(data['goal'], data['goal'])
    issues, warning = readiness(data | {'requiresProfessionalReview': consultation.requiresProfessionalReview}, consultation.patient)
    data.update(status=consultation.status, requiresProfessionalReview=consultation.requiresProfessionalReview,
        isEditable=editable(consultation), readinessIssues=issues, scopeWarning=warning,
        plans=[{'id': p.id, 'version': p.version, 'status': p.status} for p in consultation.plans or []])
    return ConsultationDetail.model_validate(data)


async def get_patient(db, patient_id):
    patient = await db.patient.find_unique(where={'id': patient_id}, include=PATIENT_INCLUDE)
    if patient is None:
        raise CaptureError(404, 'No se encontró el paciente.')
    return patient


async def get_consultation(db, consultation_id):
    consultation = await db.nutritionconsultation.find_unique(where={'id': consultation_id}, include=CONSULTATION_INCLUDE)
    if consultation is None:
        raise CaptureError(404, 'No se encontró la consulta.')
    return consultation


async def patients(db):
    rows = await db.patient.find_many(include=PATIENT_INCLUDE, order={'createdAt': 'desc'})
    return [patient_projection(p) for p in rows]


async def consultations(db, patient_id):
    await get_patient(db, patient_id)
    rows = await db.nutritionconsultation.find_many(where={'patientId': patient_id},
        include=CONSULTATION_INCLUDE, order=[{'consultationDate': 'desc'}, {'createdAt': 'desc'}])
    return [consultation_projection(c) for c in rows]


def request_hash(dto, context=''):
    payload = dto.model_dump(mode='json', exclude_unset=True)
    return hashlib.sha256((context + json.dumps(payload, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()


def check_retry(receipt, fingerprint):
    if receipt and receipt.requestHash != fingerprint:
        raise CaptureError(409, 'El identificador de guardado ya se utilizó para otros datos. Recarga el formulario.')


def check_revision(record, expected):
    if expected is not None and record.updatedAt != expected:
        raise CaptureError(409, 'Los datos cambiaron en otra sesión. Recarga la ficha antes de guardar.')


async def create_patient(db, dto, key):
    fingerprint = request_hash(dto)
    async with db.tx() as tx:
        receipt = await tx.patientcreaterequest.find_unique(where={'key': key})
        check_retry(receipt, fingerprint)
        if receipt:
            return patient_projection(await get_patient(tx, receipt.patientId))
        # Do not merge homonyms or assume age identifies a person.
        if dto.birthDate or dto.email:
            candidates = await tx.patient.find_many(where={'sex': dto.sex})
            for other in candidates:
                same_name = ' '.join(other.name.casefold().split()) == ' '.join(dto.name.casefold().split())
                same_birth = dto.birthDate and other.birthDate and dto.birthDate.date() == other.birthDate.date()
                same_email = dto.email and other.email and dto.email.casefold() == other.email.casefold()
                if same_name and (same_birth or same_email):
                    raise CaptureError(409, 'Ya existe un paciente con ese nombre y fecha de nacimiento o correo. Revisa su ficha.', other.id)
        data = dietary_create(dto.model_dump(exclude_none=True))
        if dto.age is not None:
            data['ageRecordedAt'] = now()
        created = await tx.patient.create(data=data)
        await tx.patientcreaterequest.create(data={'key': key, 'requestHash': fingerprint, 'patientId': created.id})
        return patient_projection(await get_patient(tx, created.id))


async def replace_dietary(tx, entity, entity_id, data):
    delegate = tx.patientdietaryitem if entity == 'patientId' else tx.consultationdietaryitem
    for field, kind in DIETARY_FIELDS.items():
        if field not in data:
            continue
        items = dietary_values(data.pop(field))
        await delegate.delete_many(where={entity: entity_id, 'kind': kind})
        for value in items:
            await delegate.create(data={entity: entity_id, 'kind': kind, 'content': value})


async def update_patient(db, patient_id, dto):
    async with db.tx() as tx:
        patient = await get_patient(tx, patient_id)
        check_revision(patient, dto.expectedUpdatedAt)
        data = dto.model_dump(exclude_unset=True)
        data.pop('expectedUpdatedAt', None)
        birth, age = data.get('birthDate', patient.birthDate), data.get('age', patient.age)
        if birth is not None and age is not None:
            raise CaptureError(422, 'Indica fecha de nacimiento o edad. Vacía el dato anterior para cambiar de modalidad.')
        if 'age' in data:
            data['ageRecordedAt'] = now() if data['age'] is not None else None
        await replace_dietary(tx, 'patientId', patient_id, data)
        if dto.model_fields_set - {'expectedUpdatedAt'}:
            data['updatedAt'] = now()
            await tx.patient.update(where={'id': patient_id}, data=data)
        return patient_projection(await get_patient(tx, patient_id))


def validate_capture(data, patient):
    try:
        dto = ConsultationCapture.model_validate(data)
    except ValidationError:
        raise CaptureError(422, 'Los datos de la consulta son inválidos. Revisa los campos y el presupuesto.') from None
    if dto.consultationDate is not None:
        if dto.consultationDate.date() > now().date():
            raise CaptureError(422, 'La fecha de la consulta no puede ser futura.')
        if patient.birthDate and dto.consultationDate.date() < patient.birthDate.date():
            raise CaptureError(422, 'La consulta no puede ser anterior al nacimiento.')
        if patient.birthDate and dto.ageAtConsultation is not None and dto.ageAtConsultation != current_age(patient, dto.consultationDate):
            raise CaptureError(422, 'La edad de consulta no coincide con la fecha de nacimiento.')
    issues, _ = readiness(dto.model_dump(), patient)
    if dto.status == 'READY' and issues:
        raise CaptureError(422, ' '.join(issues))
    return dto


async def create_consultation(db, patient_id, dto, key):
    fingerprint = request_hash(dto, patient_id)
    async with db.tx() as tx:
        receipt = await tx.consultationcreaterequest.find_unique(where={'key': key})
        check_retry(receipt, fingerprint)
        if receipt:
            return consultation_projection(await get_consultation(tx, receipt.consultationId))
        patient = await get_patient(tx, patient_id)
        # Preload habitual data only when omitted; explicit null/empty values clear it.
        defaults = {field: getattr(patient, source) for field, source in {
            'sex': 'sex', 'activityLevel': 'defaultActivityLevel', 'goal': 'defaultGoal',
            'mealsPerDay': 'defaultMealsPerDay', 'dailyBudget': 'defaultDailyBudget'}.items()}
        defaults['goal'] = GOAL_ALIASES.get(defaults['goal'], defaults['goal'])
        if defaults['goal'] not in set(NutritionGoal): defaults['goal'] = None
        if defaults['activityLevel'] not in set(ActivityLevel): defaults['activityLevel'] = None
        defaults.update(dietary_projection(patient.dietaryItems))
        defaults['consultationDate'] = dto.consultationDate or now()
        defaults['ageAtConsultation'] = current_age(patient, defaults['consultationDate'])
        data = defaults | dto.model_dump(exclude_unset=True)
        data['consultationDate'] = data.get('consultationDate') or now()
        valid = validate_capture(data, patient)
        created = await tx.nutritionconsultation.create(data={'patientId': patient_id, **dietary_create(valid.model_dump(exclude_none=True))})
        await tx.consultationcreaterequest.create(data={'key': key, 'requestHash': fingerprint, 'consultationId': created.id})
        return consultation_projection(await get_consultation(tx, created.id))


async def calculate_consultation(db, consultation_id):
    """Ejecuta el motor determinístico (Fase 3) y agrega un registro al historial de cálculos.

    Nunca sobrescribe un cálculo previo: cada llamada crea una nueva
    ConsultationCalculation, preservando la reproducibilidad del historial.
    No exige que la consulta esté en modo edición: un recálculo es válido
    incluso si ya existe un plan o generación asociados.
    """
    async with db.tx() as tx:
        consultation = await get_consultation(tx, consultation_id)
        data = {field: getattr(consultation, field) for field in
            ('ageAtConsultation', 'weightKg', 'heightM', 'sex', 'activityLevel', 'goal', 'mealsPerDay')}
        issues, _ = readiness(data | {'requiresProfessionalReview': consultation.requiresProfessionalReview}, consultation.patient)
        if issues:
            raise CaptureError(422, ' '.join(issues))
        try:
            result = nutrition_calculation_service.calculate(
                sex=consultation.sex, age_at_consultation=consultation.ageAtConsultation,
                weight_kg=consultation.weightKg, height_m=consultation.heightM,
                activity_level=consultation.activityLevel, goal=consultation.goal)
        except NutritionCalculationError as exc:
            raise CaptureError(400, str(exc)) from None
        details = {**result['details'], 'calculatedAt': result['calculatedAt'].isoformat()}
        await tx.consultationcalculation.create(data={
            'consultationId': consultation_id,
            'calculationMethod': result['calculationMethod'],
            'calculationRuleVersion': result['calculationRuleVersion'],
            'calculationDetails': json.dumps(details, ensure_ascii=False),
            'metrics': {'create': [{'metricCode': code, 'value': value} for code, value in result['metrics'].items()]},
        })
        return consultation_projection(await get_consultation(tx, consultation_id))


async def update_consultation(db, consultation_id, dto):
    async with db.tx() as tx:
        consultation = await get_consultation(tx, consultation_id)
        if not editable(consultation):
            raise CaptureError(409, 'Esta consulta ya no está en captura. Crea una consulta nueva para registrar cambios.')
        check_revision(consultation, dto.expectedUpdatedAt)
        changes = dto.model_dump(exclude_unset=True)
        changes.pop('expectedUpdatedAt', None)
        current = {k: getattr(consultation, k) for k in ConsultationCapture.model_fields if hasattr(consultation, k)}
        current.update(dietary_projection(consultation.dietaryItems))
        current['goal'] = GOAL_ALIASES.get(current.get('goal'), current.get('goal'))
        valid = validate_capture(current | changes, consultation.patient)
        data = valid.model_dump(exclude={'consultationDate'} if valid.consultationDate is None else set())
        await replace_dietary(tx, 'consultationId', consultation_id, data)
        data['updatedAt'] = now()
        await tx.nutritionconsultation.update(where={'id': consultation_id}, data=data)
        return consultation_projection(await get_consultation(tx, consultation_id))
