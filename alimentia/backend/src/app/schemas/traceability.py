"""Contratos de trazabilidad completa del plan (Fase 6, Parte B).

Nunca exponen prompts completos, secrets, API keys, rutas internas ni PII no
pertinente: solo identificadores técnicos y metadatos de procedencia.
"""
from datetime import datetime

from app.schemas.persistence import Contract


class TraceabilityPlan(Contract):
    id: str
    version: int
    status: str


class TraceabilityCalculation(Contract):
    calculationId: str | None = None
    method: str | None = None
    rulesetVersion: str | None = None
    recordedAt: datetime | None = None


class TraceabilityGeneration(Contract):
    generationId: str | None = None
    modelProvider: str | None = None
    modelName: str | None = None
    promptVersion: str | None = None
    generationDurationMs: int | None = None
    knowledgeBaseVersion: str | None = None


class TraceabilityResources(Contract):
    foodDatabaseUsed: bool | None = None
    foodDatabaseName: str | None = None
    foodDatabaseVersion: str | None = None
    knowledgeBaseUsed: bool | None = None


class TraceabilitySource(Contract):
    sourceId: str
    name: str
    version: str | None = None
    document: str | None = None


class TraceabilityHumanReview(Contract):
    manualEditCount: int = 0
    regenerationCount: int = 0
    approvedAt: datetime | None = None
    approvedBy: str | None = None
    rejectedAt: datetime | None = None
    rejectedBy: str | None = None


class TraceabilityValidation(Contract):
    code: str
    severity: str
    isBlocking: bool
    message: str


class PlanTraceabilityRead(Contract):
    plan: TraceabilityPlan
    calculation: TraceabilityCalculation
    generation: TraceabilityGeneration
    resources: TraceabilityResources
    sources: list[TraceabilitySource] = []
    humanReview: TraceabilityHumanReview
    validations: list[TraceabilityValidation] = []
