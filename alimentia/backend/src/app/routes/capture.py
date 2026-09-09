"""REST routes isolated from LLM/RAG startup, also used by the HTTP test app."""
from uuid import UUID, uuid4
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from prisma.errors import PrismaError
from app.repositories import capture as repo
from app.schemas.persistence import PatientCreate, PatientUpdate, Sex, ActivityLevel, NutritionGoal
from app.schemas.capture import ConsultationCapture, ConsultationUpdate, PatientDetail, ConsultationDetail
from app.schemas.generation import DietPlanGenerationResponse, GenerationJobStarted, GenerationStatusRead
from app.services import diet_plan_generation


class CaptureRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def handler(request):
            try:
                return await original(request)
            except repo.CaptureError as exc:
                return JSONResponse(status_code=exc.status,
                    content={'message': exc.message, 'existingId': exc.existing_id, **exc.extra})
            except RequestValidationError:
                return JSONResponse(status_code=422, content={'message': 'Revisa los datos ingresados y los campos obligatorios.'})
            except ValueError:
                return JSONResponse(status_code=422, content={'message': 'Los datos ingresados no tienen un formato válido.'})
            except PrismaError:
                return JSONResponse(status_code=503, content={'message': 'No fue posible guardar o cargar los datos. Inténtalo de nuevo.'})
        return handler


router = APIRouter(prefix='/api/v1', route_class=CaptureRoute)


def consultation_key(value):
    # Existing IDs are preserved verbatim; only the known migration prefix is accepted.
    UUID(value.removeprefix('legacy-consultation-'))
    return value


LABELS = {
    Sex: {'female': 'Femenino', 'male': 'Masculino'},
    ActivityLevel: {'sedentary': 'Sedentaria', 'light': 'Ligera', 'moderate': 'Moderada', 'active': 'Activa', 'very active': 'Muy activa'},
    NutritionGoal: {'WEIGHT_LOSS': 'Pérdida de peso', 'MAINTENANCE': 'Mantenimiento', 'WEIGHT_GAIN': 'Incremento de peso'},
}


def field_limits(contract):
    result = {}
    for name, spec in contract.model_json_schema()['properties'].items():
        if 'anyOf' in spec:
            spec = next((part for part in spec['anyOf'] if part.get('type') != 'null'), {})
        result[name] = {k: v for k, v in spec.items() if k in {'minimum','maximum','exclusiveMinimum','minLength','maxLength'}}
    return result


@router.get('/capture-options')
async def options():
    return {
        'sex': [{'value': v.value, 'label': LABELS[Sex][v.value]} for v in Sex],
        'activity': [{'value': v.value, 'label': LABELS[ActivityLevel][v.value]} for v in ActivityLevel],
        'goal': [{'value': v.value, 'label': LABELS[NutritionGoal][v.value]} for v in NutritionGoal],
        'patientLimits': field_limits(PatientCreate), 'consultationLimits': field_limits(ConsultationCapture),
        'scopeWarning': repo.SCOPE_WARNING,
    }


@router.get('/patients', response_model=list[PatientDetail])
async def patients(request: Request):
    return await repo.patients(request.app.state.db)


@router.get('/patients/{patient_id}', response_model=PatientDetail)
async def patient(patient_id: UUID, request: Request):
    return repo.patient_projection(await repo.get_patient(request.app.state.db, str(patient_id)))


@router.post('/patients', response_model=PatientDetail, status_code=201)
async def create_patient(dto: PatientCreate, request: Request, idempotency_key: UUID | None = Header(default=None)):
    return await repo.create_patient(request.app.state.db, dto, str(idempotency_key or uuid4()))


@router.patch('/patients/{patient_id}', response_model=PatientDetail)
async def update_patient(patient_id: UUID, dto: PatientUpdate, request: Request):
    return await repo.update_patient(request.app.state.db, str(patient_id), dto)


@router.get('/patients/{patient_id}/consultations', response_model=list[ConsultationDetail])
async def patient_consultations(patient_id: UUID, request: Request):
    return await repo.consultations(request.app.state.db, str(patient_id))


@router.post('/patients/{patient_id}/consultations', response_model=ConsultationDetail, status_code=201)
async def create_consultation(patient_id: UUID, dto: ConsultationCapture, request: Request,
    idempotency_key: UUID | None = Header(default=None)):
    return await repo.create_consultation(request.app.state.db, str(patient_id), dto, str(idempotency_key or uuid4()))


@router.get('/consultations/{consultation_id}', response_model=ConsultationDetail)
async def consultation(consultation_id: str, request: Request):
    return repo.consultation_projection(await repo.get_consultation(request.app.state.db, consultation_key(consultation_id)))


@router.patch('/consultations/{consultation_id}', response_model=ConsultationDetail)
async def update_consultation(consultation_id: str, dto: ConsultationUpdate, request: Request):
    return await repo.update_consultation(request.app.state.db, consultation_key(consultation_id), dto)


@router.post('/consultations/{consultation_id}/calculate', response_model=ConsultationDetail)
async def calculate_consultation(consultation_id: str, request: Request):
    return await repo.calculate_consultation(request.app.state.db, consultation_key(consultation_id))


@router.post('/consultations/{consultation_id}/generate-draft', response_model=DietPlanGenerationResponse)
async def generate_draft(consultation_id: str, request: Request):
    return await diet_plan_generation.generate_draft(request.app.state.db, consultation_key(consultation_id))


@router.post('/consultations/{consultation_id}/generate-draft/start', response_model=GenerationJobStarted)
async def start_generate_draft(consultation_id: str, request: Request):
    """Corrección de UX (progreso por etapas real): responde de inmediato con
    el id de la generación en curso; el frontend hace polling de
    /generations/{id}/status en vez de esperar bloqueado la respuesta."""
    generation_id = await diet_plan_generation.start_generation_job(request.app.state.db, consultation_key(consultation_id))
    return GenerationJobStarted(generationId=generation_id)


@router.get('/generations/{generation_id}/status', response_model=GenerationStatusRead)
async def get_generation_status(generation_id: str, request: Request):
    return await diet_plan_generation.get_generation_status(request.app.state.db, generation_id)
