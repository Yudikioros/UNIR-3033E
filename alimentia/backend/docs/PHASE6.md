# Fase 6 — Cierre metodológico, trazabilidad, exportación y preparación para la evaluación del MVP

Esta es la **última fase funcional** del MVP AlimentIA. No amplía el alcance
clínico, no rehace fases anteriores y no modifica el motor de cálculo de
Fase 3 ni el flujo human-in-the-loop de Fase 5 — solo los completa con
trazabilidad, métricas, exportación y una auditoría honesta de qué reglas
tienen sustento real y cuáles son decisiones del MVP.

## A. Nutrition Rule Provenance

`NUTRITION_RULESET_VERSION = "1.0"` (`app.services.nutrition_rules`, alias
directo de `calculator.RULE_VERSION` — una sola fuente de verdad, nunca
duplicada). Ninguna fórmula ni constante de `calculator.py` fue modificada;
este módulo solo las **lee y clasifica**.

| Rule | Valor actual | Clasificación | Evidencia | Notas |
|---|---|---|---|---|
| BMI | `peso_kg / talla_m²` | SOURCE_BACKED | Índice de Quetelet, fórmula estándar internacional | Solo índice descriptivo; nunca se usa como diagnóstico automático |
| MIFFLIN_ST_JEOR_BMR | Ecuación Mifflin-St Jeor (hombres +5, mujeres -161) | SOURCE_BACKED | Mifflin MD, St Jeor ST, et al. *Am J Clin Nutr.* 1990;51(2):241-247 | Cita académica externa, no vinculada a un `KnowledgeSource` del sistema |
| ACTIVITY_FACTOR | 1.20 / 1.375 / 1.55 / 1.725 / 1.90 | MVP_ASSUMPTION | Ninguna (sin fuente seleccionada en el sistema) | Nunca se presentan como "valores clínicamente validados" |
| GOAL_ENERGY_ADJUSTMENT | -500 / 0 / +300 kcal | MVP_ASSUMPTION | Ninguna | Candidato a `PROFESSIONAL_CONFIGURABLE` en una versión clínica futura |
| MACRO_DISTRIBUTION | 25% proteína / 45% CHO / 30% grasa | MVP_ASSUMPTION | Ninguna | Se mantiene fija para reproducibilidad del experimento, no como recomendación individualizada |
| FIBER_RULE | 14 g / 1000 kcal | SOURCE_BACKED | IOM (US), *Dietary Reference Intakes...* National Academies Press, 2005 | Cita académica externa, no vinculada a un `KnowledgeSource` del sistema |
| WATER_RULE | 35 ml/kg | MVP_ASSUMPTION | Ninguna (rangos publicados varían según fuente) | Candidato a `PROFESSIONAL_CONFIGURABLE` |
| ENERGY_TOLERANCE | ±5% | MVP_VALIDATION_THRESHOLD | — | Umbral de validación del MVP, no prescripción clínica; centralizado en `plan_validation.ENERGY_TOLERANCE_PERCENT` |
| INPUT_RANGES | edad 18-100, peso 20-350 kg, talla 1.20-2.30 m | TECHNICAL_GUARD | — | Límite técnico de captura, no límite clínico |

Matriz completa (con `formula`/`unit`/`sourceReference` exactos) en
`app/services/nutrition_rules.py::NUTRITION_RULE_MATRIX`, cubierta por
`tests/test_nutrition_rules.py`.

## B. Final Architecture

```
NutritionConsultation
  -> ConsultationCalculation (Fase 3: motor determinístico, rulesetVersion)
  -> FoodDatabaseService (BAM.xlsx real, si disponible)
  -> KnowledgeBaseService (RAG sobre fuentes autorizadas reales, si disponible)
  -> AIGeneration (LLM organiza y propone; nunca calcula, nunca aprueba)
  -> DietPlan (validaciones deterministas -> PlanValidation)
  -> DietPlanChangeLog (edición manual, regeneración, aprobación, rechazo)
  -> DietPlan.status = APPROVED (inmutable)
  -> GET /plans/{id}/export/pdf (solo si APPROVED)
```

Nada de esto reemplaza a Fase 3/4/5: `PlanTraceabilityRead` y
`EvaluationMetricsRead` son **proyecciones de lectura** sobre datos ya
persistidos, no nuevas tablas de estado.

## C. Traceability

`GET /api/v1/plans/{plan_id}/traceability` reconstruye consulta → cálculo →
ruleset → base alimentaria → conocimiento recuperado → generación IA →
validaciones → intervención humana → aprobación/rechazo, sin exponer
prompts completos, secrets, rutas internas ni el UUID del paciente.

Ejemplo real (plan v3 de María González, aprobado):

```json
{
  "plan": {"version": 3, "status": "APPROVED"},
  "calculation": {"method": "MIFFLIN_ST_JEOR", "rulesetVersion": "1.0"},
  "generation": {"modelProvider": "ollama", "modelName": "llama3.2:3b",
    "promptVersion": "1.0", "generationDurationMs": 443131, "knowledgeBaseVersion": "2.0"},
  "sources": [
    {"name": "Guía de Alimentos para la Población Mexicana", "document": "Guía de alimentos SS.pdf"},
    {"name": "Guías alimentarias y de actividad física...", "document": "Guías Alimentarias.pdf"}
  ],
  "humanReview": {"manualEditCount": 1, "regenerationCount": 0,
    "approvedAt": "2026-09-07T09:05:58Z", "approvedBy": "dra-lopez"},
  "validations": [{"code": "ENERGY_WITHIN_TOLERANCE", "isBlocking": false}]
}
```

`resources.foodDatabaseUsed`/`knowledgeBaseUsed` son `null` para
generaciones anteriores a la migración `202609070001_generation_resource_flags`
(nunca se infiere retroactivamente lo que no se registró en su momento).

## D. Evaluation Metrics

`GET /api/v1/plans/{plan_id}/evaluation-metrics` — individual por caso, sin
dashboard agregado (fuera de alcance del MVP). Todo derivado de datos
existentes (`AIGeneration`, `DietPlan`, `DietPlanChangeLog`,
`PlanValidation`, `PlanNutrientObservation`, `ConsultationCalculation`,
`RetrievedSource`); ninguna tabla nueva.

Resultado real del caso de demostración (consulta de María González,
versiones 1→3):

| Métrica | Valor |
|---|---|
| generationCount | 3 |
| regenerationCount | 1 |
| manualEditCount | 1 |
| versionCount | 3 |
| initialPlanVersion → finalPlanVersion | 1 → 3 |
| approvedVersion | 3 |
| initialEnergyDeviationPercent | -91.1% (v1: 150 kcal vs. 1686 kcal objetivo) |
| finalEnergyDeviationPercent | -1.58% (v3 editada: 1659 kcal) |
| initialBlockingValidationCount → finalBlockingValidationCount | 2 → 0 |
| initialMealCount → finalMealCount | 1 → 5 |
| retrievedSourceCount | 3 |
| modelName / promptVersion / calculationRuleVersion | llama3.2:3b / 1.0 / 1.0 |

### C.1 Métricas automáticas vs. experimentales (sección 19)

**A. Automáticas** (disponibles hoy, sin intervención adicional): generación
LLM, tiempo de inferencia, desviación energética, número de comidas,
validaciones, ediciones, regeneraciones, fuentes, versión aprobada, tiempo
generación→aprobación.

**B. Experimentales** (NO disponibles automáticamente, nunca inventadas):
tiempo manual del nutriólogo sin AlimentIA, satisfacción, utilidad
percibida, calidad clínica por evaluador, acuerdo entre nutriólogos. Ver
`EVALUATION_PROTOCOL.md` para cómo medirlas en un estudio posterior.

## E. Export

`GET /api/v1/plans/{plan_id}/export/pdf` — solo `status == APPROVED`; DRAFT,
UNDER_REVIEW y REJECTED devuelven `409`. Generado con `fpdf2` (nueva
dependencia mínima; no había ninguna librería de generación de PDF en el
proyecto). Incluye: identificación del paciente, fecha, versión, estado
APROBADO, profesional que aprobó, objetivo nutricional completo, comidas y
alimentos con cantidades y notas, recomendaciones (si el LLM las generó —
sección "Deuda técnica"), y solo las fuentes documentales realmente
recuperadas para esa generación (nunca el catálogo completo). Nunca incluye
UUIDs, prompts, logs, scores de embeddings ni metadata técnica.

Validado con datos reales (plan v3 de María, aprobado): PDF de 2 páginas,
contenido verificado extrayendo el texto con `pypdf` — paciente, objetivo,
5 comidas con 11 alimentos y sus notas de verificación BAM, y las 2 fuentes
documentales realmente recuperadas.

**Defecto real encontrado y corregido durante esta fase**: `fpdf2` puede
lanzar `FPDFException("Not enough horizontal space...")` en escenarios reales
(reproducido con datos reales de la app, no solo con texto exótico),
aparentemente por un cálculo de ancho disponible cerca de un salto de página
automático. Se agregó saneamiento de texto (`_safe()`, para puntuación
tipográfica del LLM fuera de Latin-1) y una recuperación defensiva
(`_multi_cell()`: fuerza una página nueva y reintenta una vez) para que la
exportación nunca responda `500`.

## F. Demonstration Case

Consulta de María González (`6b32a5d9-...`, adulta general, WEIGHT_LOSS,
objetivo 1685.89 kcal/1.0 ruleset), sin alterar v1/v2 preexistentes:

1. **v1** (preexistente): 150 kcal, 1 comida — `MEAL_COUNT_MISMATCH` +
   `ENERGY_OUT_OF_TOLERANCE` bloqueantes.
2. **v2** (preexistente): datos nutricionales incompletos —
   `INCOMPLETE_NUTRITION_DATA` bloqueante.
3. **v3** (generación real, Ollama/llama3.2:3b, 443.1s, `foodDatabaseUsed=true`,
   `knowledgeBaseUsed=true`, 3 fuentes recuperadas): 5 comidas, 11 alimentos,
   pero **0 de 11 verificados automáticamente contra BAM** — el LLM usó
   unidades caseras (taza/pieza) en vez de gramos, y la precedencia BAM > LLM
   (sección 24 de la etapa previa) solo aplica a coincidencias exactas en
   gramos — `INCOMPLETE_NUTRITION_DATA` bloqueante (faltaban calorías).
4. **Regeneración solicitada** con instrucciones ("usa gramos, asegura
   energía suficiente") — el intento real chocó dos veces con el problema ya
   documentado de generaciones huérfanas de Ollama bajo carga (502 tras
   >20 min); no se forzó una alternativa artificial.
5. **Edición profesional de v3** (`manualEditCount=1`): se convirtieron las
   11 cantidades de unidades caseras a gramos usando equivalencias estándar
   de porción, y se verificó cada alimento contra BAM real (búsqueda exacta
   por nombre, ver tabla abajo). Un alimento ("Pescado") se precisó a
   "Pescado (tilapia)" para poder verificarlo con una entrada real de BAM —
   corrección de estructura explícita, documentada en la nota del alimento,
   nunca silenciosa.
6. Resultado: 1659.2 kcal, desviación -1.58% (`ENERGY_WITHIN_TOLERANCE`,
   0 validaciones bloqueantes) → **aprobado** por `dra-lopez`.

| Alimento | Cantidad final | BAM (codigomex2) | kcal/100g real |
|---|---|---|---|
| Avena | 180 g | AVENA (HOJUELAS), 12007 | 373 |
| Manzana | 200 g | MANZANA RED DELICIOUS, 16064 | 52 |
| Plátano | 150 g | PLATANO TABASCO, 16096 | 89 |
| Lechuga | 200 g | LECHUGA ROMANA, 17123 | 14 |
| Tomate | 200 g | JITOMATE SALADET, 17120 | 18 |
| Zanahoria | 150 g | ZANAHORIA, 17158 | 41 |
| Yogur | 300 g | YOGURT NATURAL (LECHE ENTERA), 10162 | 82.8 |
| Fresa | 200 g | FRESA, 16030 | 32 |
| Pescado (tilapia) | 250 g | PESCADO FRESCO, TILAPIA, 8035 | 96 |
| Brócoli | 200 g | BROCOLI COCIDO, 17017 | 35 |
| Té de manzanilla | 240 g | TE DE MANZANILLA, INFUSION, 5178 | 1 |

`smaeEquivalent` permaneció `null` en los 11 alimentos, en los 3 (v1/v2/v3):
nunca se inventó una equivalencia SMAE. La aprobación se logró exclusivamente
mediante corrección de estructura, cantidades y valores nutrimentales
verificables — nunca cambiando `ENERGY_TOLERANCE_PERCENT`, los rangos
técnicos de captura, ni ninguna regla de bloqueo.

## G. Known Limitations

- El modelo `llama3.2:3b` en CPU puede producir borradores incompletos
  (unidades caseras en vez de gramos, valores nutricionales faltantes) —
  observado directamente en v3 de este mismo caso.
- Inferencia CPU lenta (~440s por generación real observados en esta fase) y
  con riesgo conocido de generaciones huérfanas bajo carga (dos intentos de
  regeneración de este caso fallaron por esa razón).
- Equivalencias SMAE no estructuradas: `smaeEquivalent` seguirá `null` hasta
  que exista una fuente tabular limpia o una herramienta de extracción con
  reconocimiento de layout (ver `REAL_RESOURCES_INTEGRATION.md`).
- Validación SMAE determinística no implementada.
- Reglas nutricionales del MVP sin fuente formal seleccionada en el sistema
  (`ACTIVITY_FACTOR`, `GOAL_ENERGY_ADJUSTMENT`, `MACRO_DISTRIBUTION`,
  `WATER_RULE`) — ver matriz de la Parte A.
- Alcance limitado a adultos sin patologías clínicas complejas.
- Documentos `NOT_USABLE`: `GUÍAS ALIMENTARIAS 2.pdf`, `TC ácidos grasos.pdf`
  (corruptos, nunca incorporados).
- El RAG depende de que los documentos autorizados estén presentes en disco;
  sin ellos, `knowledgeBaseUsed=false` de forma honesta, no simulada.
- La precedencia BAM > LLM en generación automática solo aplica a
  coincidencias exactas de nombre en gramos: en la práctica, pocos alimentos
  generados por el LLM califican automáticamente (confirmado: 0/11 en la
  generación real de este caso). La verificación completa de un plan típico
  sigue requiriendo revisión profesional activa, no solo automatización.
- `config/page.tsx` (frontend) sigue con datos estáticos de ejemplo, sin
  fetch al backend — no se tocó por no ser ampliación de soporte existente.
- Revisión profesional obligatoria: el sistema nunca aprueba nada por sí
  mismo, ni siquiera cuando todas las validaciones pasan.

## H. Evaluation Readiness

- ✅ Flujo completo funciona (captura → cálculo → generación → revisión →
  aprobación → exportación), demostrado con un caso real de principio a fin.
- ✅ BAM real funciona (18.1.1/2021, 2045 filas).
- ✅ RAG real funciona (4 documentos activos, 424 puntos indexados).
- ✅ Reglas clasificadas y versionadas (`NUTRITION_RULESET_VERSION = "1.0"`,
  9 reglas auditadas).
- ✅ Cálculos trazables (`ConsultationCalculation` + `calculationRuleVersion`).
- ✅ Generación trazable (`AIGeneration` + `foodDatabaseUsed`/`knowledgeBaseUsed`
  explícitos desde esta fase).
- ✅ Fuentes reales (nunca un documento no autorizado; trazabilidad completa
  slug → UUID → `KnowledgeSource`).
- ✅ Validaciones funcionan (bloqueantes/no bloqueantes, sección 11 de
  Fase 5, sin cambios).
- ✅ Intervención humana auditada (`DietPlanChangeLog`, `manualEditCount`/
  `regenerationCount` contando guardados reales, no filas internas).
- ✅ Aprobación protegida y aprobado inmutable (sin cambios respecto a Fase 5).
- ✅ PDF final se genera para planes aprobados, validado con datos reales.
- ✅ Métricas derivables por caso.
- ✅ Protocolo de evaluación existe (`EVALUATION_PROTOCOL.md`), sin estudio
  ficticio ejecutado.
- ✅ Historial intacto (4 pacientes, 6 planes totales, preservados en cada
  migración).
- ✅ 239/239 pruebas pasan en Docker real.
- ✅ Frontend compila (`npm run build`) y pasa lint (`npm run lint`) sin errores.
- ✅ No existen datos inventados: cada valor SOURCE_BACKED cita una
  referencia real; cada MVP_ASSUMPTION lo declara explícitamente; SMAE nunca
  se afirma "validado".

---

**EL DESARROLLO FUNCIONAL DEL MVP ALIMENTIA HA TERMINADO.**

No se crea Fase 7.
