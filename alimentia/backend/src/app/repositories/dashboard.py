"""
Resumen operativo (`/`): agregaciones reales sobre pacientes, consultas y
planes. Nunca inventa cifras -si no hay datos suficientes, el valor es
`None`/0 real, nunca un placeholder disfrazado de dato-.

Una sola consulta Prisma (con includes anidados) trae todo lo necesario;
el resto es agregación en Python sobre esa misma estructura -mismo patrón
que `app.repositories.capture.patient_projection`-, evitando N+1 desde
frontend y round-trips adicionales a la base de datos.
"""
from datetime import timezone

from app.repositories.capture import current_age
from app.repositories.plan_management import EDITABLE_STATUSES
from app.schemas.dashboard import DashboardMetrics, DashboardPatientRow, DashboardPendingPlan, DashboardSummary

PENDING_PLANS_LIMIT = 5

DASHBOARD_INCLUDE = {
    "consultations": {
        "include": {
            "plans": {
                "include": {"generationLinks": {"include": {"generation": True}}},
            },
        },
    },
}


def _latest_plan(plans):
    """DietPlan con mayor `version` dentro de una consulta (sección 14).
    Desempate determinístico por `createdAt` y luego `id` para cualquier
    caso legado/imposible donde dos versiones compartieran número."""
    if not plans:
        return None
    return max(plans, key=lambda plan: (plan.version, plan.createdAt, plan.id))


def _latest_consultation(consultations):
    """Última consulta de un paciente por `consultationDate` real (sección
    13), nunca por el orden en que Prisma devuelva las filas. Desempate por
    `createdAt` y `id`."""
    if not consultations:
        return None
    return max(consultations, key=lambda c: (c.consultationDate, c.createdAt, c.id))


def _generated_at(plan):
    """Mismo criterio ya usado en el detalle de plan
    (`plan_management._plan_detail`): la fecha de generación real es la del
    `AIGeneration` de origen, no `DietPlan.createdAt` (que en el pipeline de
    progreso por etapas se persiste recién al terminar, no al iniciar)."""
    origin = next((link for link in plan.generationLinks or [] if link.isOrigin), None)
    return origin.generation.createdAt if origin and origin.generation else None


async def get_dashboard_summary(db) -> DashboardSummary:
    patients = await db.patient.find_many(include=DASHBOARD_INCLUDE, order={"createdAt": "desc"})

    registered_patients = len(patients)
    generated_plans = await db.dietplan.count()

    pending_review = 0
    approved_plans = 0
    pending_candidates: list[tuple] = []  # (patient, consultation, latest_plan)
    review_durations: list[float] = []

    for patient in patients:
        for consultation in patient.consultations or []:
            latest = _latest_plan(consultation.plans or [])
            if latest is None:
                continue
            if latest.status in EDITABLE_STATUSES:  # {"DRAFT", "UNDER_REVIEW"}
                pending_review += 1
                pending_candidates.append((patient, consultation, latest))
            elif latest.status == "APPROVED":
                approved_plans += 1

            if latest.status == "APPROVED" and latest.approvedAt is not None:
                generated_at = _generated_at(latest)
                if generated_at is not None:
                    delta = (latest.approvedAt.replace(tzinfo=timezone.utc) - generated_at.replace(tzinfo=timezone.utc)).total_seconds()
                    if delta >= 0:
                        review_durations.append(delta)

    average_review_seconds = (sum(review_durations) / len(review_durations)) if review_durations else None

    recent_patients = []
    for patient in patients:
        latest_consultation = _latest_consultation(patient.consultations or [])
        latest_plan = _latest_plan(latest_consultation.plans or []) if latest_consultation else None
        recent_patients.append(DashboardPatientRow(
            id=patient.id, name=patient.name, currentAge=current_age(patient), isDemo=patient.demoKey is not None,
            goal=latest_consultation.goal if latest_consultation else None,
            latestConsultationDate=latest_consultation.consultationDate if latest_consultation else None,
            latestPlanId=latest_plan.id if latest_plan else None,
            latestPlanVersion=latest_plan.version if latest_plan else None,
            latestPlanStatus=latest_plan.status if latest_plan else None,
        ))

    pending_candidates.sort(key=lambda item: item[2].createdAt, reverse=True)
    pending_plans = [
        DashboardPendingPlan(planId=latest.id, patientId=patient.id, patientName=patient.name,
                              version=latest.version, status=latest.status, generatedAt=_generated_at(latest))
        for patient, _consultation, latest in pending_candidates[:PENDING_PLANS_LIMIT]
    ]

    return DashboardSummary(
        metrics=DashboardMetrics(
            registeredPatients=registered_patients, generatedPlans=generated_plans,
            pendingReview=pending_review, approvedPlans=approved_plans,
            averageReviewTimeSeconds=average_review_seconds,
        ),
        recentPatients=recent_patients, pendingPlans=pending_plans, pendingPlansTotal=pending_review,
    )
