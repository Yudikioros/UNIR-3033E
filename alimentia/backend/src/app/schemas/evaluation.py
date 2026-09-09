"""Contrato de métricas de evaluación por caso (Fase 6, Parte C).

Solo expone métricas AUTOMÁTICAS, reconstruidas de datos ya persistidos.
Nunca inventa métricas experimentales (tiempo manual, satisfacción, calidad
clínica): esas se documentan aparte como pendientes académicos.
"""
from app.schemas.persistence import Contract


class EvaluationMetricsRead(Contract):
    consultationId: str
    planId: str
    generationCount: int = 0
    regenerationCount: int = 0
    manualEditCount: int = 0
    versionCount: int = 0
    initialPlanVersion: int | None = None
    finalPlanVersion: int | None = None
    approvedVersion: int | None = None
    generationDurationMs: int | None = None
    timeFromFirstGenerationToApprovalSeconds: float | None = None
    initialEnergyDeviationPercent: float | None = None
    finalEnergyDeviationPercent: float | None = None
    initialBlockingValidationCount: int | None = None
    finalBlockingValidationCount: int | None = None
    initialMealCount: int | None = None
    finalMealCount: int | None = None
    knowledgeBaseUsed: bool | None = None
    foodDatabaseUsed: bool | None = None
    retrievedSourceCount: int = 0
    modelName: str | None = None
    promptVersion: str | None = None
    calculationRuleVersion: str | None = None
