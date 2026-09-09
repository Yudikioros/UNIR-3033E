"""Contratos del resumen operativo (`/`).

Cada campo tiene una definición precisa y verificable contra la base de
datos real -nunca una cifra inventada- documentada junto a su cálculo en
`app.repositories.dashboard`."""
from datetime import datetime

from pydantic import Field

from app.schemas.persistence import Contract


class DashboardMetrics(Contract):
    # COUNT real de Patient. Nunca cuenta consultas ni planes.
    registeredPatients: int
    # COUNT real de DietPlan (todas las versiones de todas las consultas).
    generatedPlans: int
    # Número de CONSULTAS cuya versión de plan más reciente está en DRAFT o
    # UNDER_REVIEW (una consulta con v1 DRAFT + v2 APPROVED no cuenta aquí).
    pendingReview: int
    # Número de CONSULTAS cuya versión de plan más reciente está APPROVED.
    approvedPlans: int
    # Promedio de (DietPlan.approvedAt - AIGeneration.createdAt del origen)
    # en segundos, solo para planes APPROVED con ambos timestamps válidos
    # (diferencia no negativa). `null` si no hay datos suficientes -nunca 0-.
    averageReviewTimeSeconds: float | None = None


class DashboardPatientRow(Contract):
    id: str
    name: str
    currentAge: int | None = None
    isDemo: bool
    # Objetivo de la CONSULTA más reciente del paciente (no el objetivo
    # habitual del paciente). `null` si el paciente no tiene consultas.
    goal: str | None = None
    latestConsultationDate: datetime | None = None
    latestPlanId: str | None = None
    latestPlanVersion: int | None = None
    # Estado de la versión más reciente del plan de la consulta más
    # reciente. `null` si la consulta todavía no tiene ningún DietPlan.
    latestPlanStatus: str | None = None


class DashboardPendingPlan(Contract):
    planId: str
    patientId: str
    patientName: str
    version: int
    status: str
    generatedAt: datetime | None = None


class DashboardSummary(Contract):
    metrics: DashboardMetrics
    recentPatients: list[DashboardPatientRow] = Field(default_factory=list)
    pendingPlans: list[DashboardPendingPlan] = Field(default_factory=list)
    # Total real de consultas pendientes (puede ser mayor que len(pendingPlans),
    # que se limita a un máximo razonable para el panel).
    pendingPlansTotal: int = 0
