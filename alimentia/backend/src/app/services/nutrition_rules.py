"""
Matriz de trazabilidad de reglas nutricionales (Fase 6, Parte A).

Auditoría metodológica del motor determinístico de Fase 3: no cambia ninguna
fórmula, constante ni resultado histórico. Este módulo solo LEE las
constantes ya centralizadas en `calculator.py` y las clasifica según su
sustento real -nunca asume que una constante es clínicamente válida solo
porque ya existe en código-.

Clasificaciones (`evidenceStatus`), sin fuentes inventadas:

    SOURCE_BACKED               referencia académica/normativa real y verificable
    MVP_ASSUMPTION              regla de uso común, sin fuente seleccionada en el sistema
    PROFESSIONAL_CONFIGURABLE   candidata a exponerse como parámetro editable en el futuro
    TECHNICAL_GUARD             límite técnico de captura, no un límite clínico
    MVP_VALIDATION_THRESHOLD    umbral de validación del MVP, no una prescripción clínica
"""
from app.services import calculator

NUTRITION_RULESET_VERSION = calculator.RULE_VERSION


class EvidenceStatus:
    SOURCE_BACKED = "SOURCE_BACKED"
    MVP_ASSUMPTION = "MVP_ASSUMPTION"
    PROFESSIONAL_CONFIGURABLE = "PROFESSIONAL_CONFIGURABLE"
    TECHNICAL_GUARD = "TECHNICAL_GUARD"
    MVP_VALIDATION_THRESHOLD = "MVP_VALIDATION_THRESHOLD"


def _rule(rule_id, name, formula, unit, evidence_status, source_reference, notes):
    return {
        "ruleId": rule_id, "name": name, "version": NUTRITION_RULESET_VERSION,
        "formula": formula, "unit": unit, "evidenceStatus": evidence_status,
        "sourceReference": source_reference, "implementationStatus": "IMPLEMENTED", "notes": notes,
    }


_activity_factors_str = ", ".join(
    f"{level.value}={factor}" for level, factor in calculator.ACTIVITY_FACTORS.items())
_goal_adjustments_str = ", ".join(
    f"{goal.value}={adj:+.0f} kcal" for goal, adj in calculator.GOAL_ADJUSTMENTS_KCAL.items())
_macro_str = ", ".join(
    f"{name}={pct:.0f}%" for name, pct in calculator.MACRO_DISTRIBUTION_PERCENTAGE.items())

NUTRITION_RULE_MATRIX = [
    _rule(
        "BMI", "Índice de Masa Corporal (IMC)",
        "peso_kg / talla_m^2", "kg/m2",
        EvidenceStatus.SOURCE_BACKED,
        "Índice de Quetelet (IMC): fórmula estándar internacional de uso descriptivo.",
        "Se calcula y se registra únicamente como índice descriptivo del MVP; nunca se "
        "convierte automáticamente en diagnóstico clínico ni se usa para decidir el plan.",
    ),
    _rule(
        "MIFFLIN_ST_JEOR_BMR", "Tasa metabólica basal (Mifflin-St Jeor)",
        "Hombres: 10*peso_kg + 6.25*talla_cm - 5*edad + 5 | "
        "Mujeres: 10*peso_kg + 6.25*talla_cm - 5*edad - 161", "kcal/día",
        EvidenceStatus.SOURCE_BACKED,
        "Mifflin MD, St Jeor ST, et al. \"A new predictive equation for resting energy "
        "expenditure in healthy individuals.\" Am J Clin Nutr. 1990;51(2):241-247.",
        "Referencia académica original de la fórmula que le da nombre. No está vinculada a "
        "un KnowledgeSource del sistema (no forma parte del manifiesto RAG de Fase 3.5): es "
        "una cita bibliográfica externa, no un documento indexado. No se han modificado "
        "resultados históricos ya calculados y persistidos.",
    ),
    _rule(
        "ACTIVITY_FACTOR", "Factor de actividad física (multiplicador de TDEE)",
        f"TDEE = BMR × factor. Factores: {_activity_factors_str}", "adimensional",
        EvidenceStatus.MVP_ASSUMPTION, None,
        "Valores de uso extendido en la estimación de TDEE, pero sin una fuente explícita y "
        "verificable seleccionada en este sistema. No se presentan como 'valores clínicamente "
        "validados'. Candidatos a volverse PROFESSIONAL_CONFIGURABLE en una versión clínica futura.",
    ),
    _rule(
        "GOAL_ENERGY_ADJUSTMENT", "Ajuste de energía objetivo por meta",
        f"energía_objetivo = TDEE + ajuste. Ajustes: {_goal_adjustments_str}", "kcal/día",
        EvidenceStatus.MVP_ASSUMPTION, None,
        "Regla del MVP, no una prescripción clínica individualizada. Sin fuente seleccionada "
        "explícitamente en el sistema. En una versión clínica futura debería ser configurable "
        "por el profesional caso por caso.",
    ),
    _rule(
        "MACRO_DISTRIBUTION", "Distribución porcentual de macronutrientes",
        f"gramos = (energía_objetivo × %) / kcal_por_gramo. Distribución: {_macro_str}", "%",
        EvidenceStatus.MVP_ASSUMPTION, None,
        "No se asume una distribución universalmente válida para cualquier paciente; se "
        "mantiene fija para la reproducibilidad del experimento del MVP, no como recomendación "
        "clínica individualizada.",
    ),
    _rule(
        "FIBER_RULE", "Fibra dietética objetivo",
        f"fibra_g = energía_objetivo / 1000 × {calculator.FIBER_G_PER_1000_KCAL:g}", "g/día",
        EvidenceStatus.SOURCE_BACKED,
        "Institute of Medicine (US), Panel on Macronutrients. \"Dietary Reference Intakes for "
        "Energy, Carbohydrate, Fiber, Fat, Fatty Acids, Cholesterol, Protein, and Amino Acids.\" "
        "National Academies Press, 2005 — regla de referencia de 14 g de fibra por cada 1000 kcal.",
        "Referencia académica externa; no vinculada a un KnowledgeSource del sistema (no forma "
        "parte del manifiesto RAG de Fase 3.5).",
    ),
    _rule(
        "WATER_RULE", "Agua simple objetivo",
        f"agua_ml = peso_kg × {calculator.WATER_ML_PER_KG:g}", "ml/día",
        EvidenceStatus.MVP_ASSUMPTION, None,
        "Regla de uso común en orientación nutricional general, pero sin una única fuente "
        "canónica verificable seleccionada en este sistema (los rangos publicados varían según "
        "la fuente). Buena candidata a PROFESSIONAL_CONFIGURABLE en una versión clínica futura, "
        "donde el profesional pueda ajustar el criterio por paciente.",
    ),
    _rule(
        "ENERGY_TOLERANCE", "Tolerancia de desviación energética del plan",
        f"|kcal_plan - energía_objetivo| / energía_objetivo <= {5.0:g}%", "%",
        EvidenceStatus.MVP_VALIDATION_THRESHOLD, None,
        "Umbral de validación determinística del MVP (Fase 4/5) para decidir si el borrador "
        "generado por el LLM se acerca lo suficiente al objetivo calculado; no es una "
        "prescripción clínica. Centralizado en `plan_validation.ENERGY_TOLERANCE_PERCENT`.",
    ),
    _rule(
        "INPUT_RANGES", "Rangos técnicos de captura (edad, peso, talla)",
        f"edad: {calculator.AGE_RANGE_YEARS[0]}-{calculator.AGE_RANGE_YEARS[1]} años | "
        f"peso: {calculator.WEIGHT_RANGE_KG[0]:g}-{calculator.WEIGHT_RANGE_KG[1]:g} kg | "
        f"talla: {calculator.HEIGHT_RANGE_M[0]:g}-{calculator.HEIGHT_RANGE_M[1]:g} m",
        "años / kg / m",
        EvidenceStatus.TECHNICAL_GUARD, None,
        "Límites técnicos de captura para evitar cálculos sin sentido numérico (p.ej. edad "
        "negativa), no límites clínicos de inclusión/exclusión de pacientes.",
    ),
]


def rule_matrix() -> list[dict]:
    """Copia de la matriz de reglas para exponer o documentar (nunca se muta la fuente)."""
    return [dict(rule) for rule in NUTRITION_RULE_MATRIX]
