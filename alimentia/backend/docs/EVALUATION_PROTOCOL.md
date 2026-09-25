# Protocolo de evaluación académica de AlimentIA (Fase 6, Parte F)

Este documento define **cómo** se evaluará AlimentIA en un estudio posterior.
No ejecuta ningún estudio: no hay participantes, no hay datos de sujetos, no
hay resultados. Los valores de métricas experimentales (tiempo manual,
satisfacción, calidad clínica evaluada por profesional) que aparecen aquí son
**placeholders de diseño**, nunca datos reales.

## 1. Objetivo

Determinar si AlimentIA (motor determinístico + BAM + RAG + LLM +
validaciones deterministas + revisión humana obligatoria) reduce el tiempo de
elaboración de un plan alimentario de primera versión frente a la
elaboración manual, sin degradar la calidad clínica percibida por el
profesional, en el alcance del MVP (adultos sin patologías clínicas
complejas).

No se evalúa "el LLM solo": se evalúa el sistema completo, incluyendo la
intervención obligatoria del nutriólogo.

## 2. Diseño

Estudio comparativo intra-sujeto (cada nutriólogo participante resuelve
casos con ambas condiciones, en orden contrabalanceado para controlar el
efecto de aprendizaje) o entre-sujetos si el número de profesionales
disponibles no permite contrabalanceo. Diseño exploratorio/piloto, no
un ensayo clínico: el objetivo es caracterizar el prototipo, no demostrar
superioridad estadística definitiva con una muestra pequeña.

## 3. Población / casos

- Casos sintéticos o anonimizados de pacientes adultos sin patologías
  clínicas complejas (mismo alcance que el MVP: sección 45 de PHASE6.md).
- Un mismo conjunto de casos se resuelve en ambas condiciones (manual y
  asistida), nunca el mismo caso resuelto dos veces por el mismo profesional
  en la misma condición.
- Número de casos y de profesionales participantes: a definir por quien
  ejecute el estudio; este documento no fija una `n` porque no fue provista
  y no debe inventarse.

## 4. Procedimiento

1. Se presenta al profesional el mismo caso clínico base (datos
   antropométricos, objetivo, preferencias, restricciones) en ambas
   condiciones.
2. **Condición manual**: el profesional elabora el plan con sus herramientas
   habituales (hoja de cálculo, tablas de composición impresas/digitales,
   criterio propio), sin AlimentIA.
3. **Condición AlimentIA asistida**: el profesional captura el caso en
   AlimentIA, genera un borrador, y lo revisa/edita/aprueba usando el flujo
   human-in-the-loop existente (Fase 5).
4. Se registra el tiempo y las métricas automáticas (sección 6) en ambas
   condiciones.
5. Al finalizar cada condición, el profesional completa la rúbrica de
   calidad (sección 8).

## 5. Condición manual vs. condición AlimentIA (qué se compara)

    MANUAL                         vs        ALIMENTIA ASISTIDO
    (criterio + tablas propias)              (motor determinístico + BAM
                                              + RAG + LLM + validaciones
                                              deterministas + nutriólogo)

**Nunca** se compara "LLM solo" contra "nutriólogo solo": AlimentIA es el
sistema completo, incluida la revisión humana obligatoria. Comparar
únicamente la salida cruda del LLM sin el resto del pipeline no representa
lo que el prototipo realmente es ni cómo se usaría en la práctica.

## 6. Variables / métricas automáticas (ya instrumentadas)

Disponibles sin intervención adicional vía `GET /plans/{id}/evaluation-metrics`
y `GET /plans/{id}/traceability` (Fase 6, Partes B y C):

- Tiempo de generación (LLM) por versión (`generationDurationMs`).
- Tiempo desde la primera generación hasta la aprobación
  (`timeFromFirstGenerationToApprovalSeconds`).
- Desviación energética inicial y final (`initialEnergyDeviationPercent`,
  `finalEnergyDeviationPercent`).
- Número de comidas inicial y final.
- Número de validaciones bloqueantes inicial y final.
- Número de ediciones manuales (guardados) y de regeneraciones solicitadas.
- Versión inicial, versión final, versión aprobada (si la hay).
- Fuentes documentales recuperadas y usadas (`retrievedSourceCount`,
  `knowledgeBaseUsed`).
- Uso de BAM estructurado (`foodDatabaseUsed`).
- Modelo, `promptVersion`, `calculationRuleVersion` usados.

Para la condición manual no existe instrumentación automática: el tiempo y
los errores se registran con el instrumento de la sección 7.

## 7. Instrumento de registro

Para la condición manual (sin AlimentIA), se sugiere una planilla mínima por
caso con: hora de inicio, hora de término, número de comidas del plan
resultante, desviación energética estimada por el propio profesional
(si la calcula), número de correcciones/replanteamientos que el profesional
hizo sobre su propio primer borrador, y observaciones libres. Este
instrumento no está implementado en el sistema: es papel/hoja de cálculo
externa al alcance del MVP.

## 8. Intervención del nutriólogo

En la condición AlimentIA, la intervención humana es constitutiva del
sistema (Fase 5): el borrador nunca se considera un resultado final por sí
mismo. Se registra qué tipo de intervención ocurrió (edición de estructura,
de cantidades, de valores nutrimentales, regeneración, rechazo) vía
`DietPlanChangeLog`, expuesto en `traceability.humanReview`.

## 9. Manejo de errores

- Un caso que produce un `500`/error no controlado se descarta del análisis
  y se reporta aparte como incidente técnico, no como "peor desempeño".
- Un caso bloqueado por validaciones deterministas que el profesional no
  logra resolver dentro de un número razonable de regeneraciones/ediciones
  (a definir por quien ejecute el estudio) se registra como "no aprobado en
  la sesión", no se fuerza su aprobación cambiando reglas de validación.
- Nunca se relajan `ENERGY_TOLERANCE_PERCENT`, los rangos técnicos de
  captura, ni ninguna validación bloqueante para conseguir que un caso
  "pase": eso invalidaría la medición.

## 10. Trazabilidad del estudio

Cada caso del estudio corresponde a una `NutritionConsultation` y su cadena
de `DietPlan` real en el sistema; el resultado de cada caso es 100%
reconstruible después vía `GET /plans/{id}/traceability` y
`GET /plans/{id}/evaluation-metrics` — no se depende de que quien ejecute el
estudio tome notas paralelas para poder auditar qué pasó.

---

## Métricas principales (sección 33 de PHASE6.md)

1. Tiempo total de elaboración (manual vs. asistido).
2. Desviación energética del plan final.
3. Cumplimiento de macronutrientes, cuando existan datos suficientes
   (`INCOMPLETE_NUTRITION_DATA` ausente).
4. Número de errores/validaciones bloqueantes encontradas.
5. Completitud (número de comidas / alimentos con datos nutricionales).
6. Número de intervenciones manuales.
7. Número de regeneraciones.
8. Fuentes documentales recuperadas.
9. Versión finalmente aprobada.
10. Evaluación profesional del resultado (rúbrica, sección 12).

## SMAE como métrica (sección 34)

**No se afirma "adherencia SMAE automatizada".** AlimentIA no implementa
todavía validación determinística de equivalentes SMAE: `smaeEquivalent` es
`null` salvo que en el futuro exista una fuente estructurada confiable (ver
"Limitaciones conocidas" en PHASE6.md). En este protocolo, SMAE solo puede
evaluarse como criterio profesional/documental por el propio nutriólogo al
calificar el plan (p.ej. "¿las porciones sugeridas son razonables desde el
criterio SMAE del profesional?"), nunca como una métrica automática del
sistema.

## Calidad clínica (sección 35)

AlimentIA no se autoasigna una calificación clínica: la calidad final la
evalúa el profesional. Rúbrica conceptual sugerida (escala 1-5 por variable,
a definir/ajustar por quien ejecute el estudio; ningún valor por defecto
implica una calificación real):

| Variable | Pregunta guía |
|---|---|
| Pertinencia | ¿El plan es adecuado para el objetivo y preferencias del caso? |
| Seguridad | ¿Respeta restricciones/alergias declaradas sin excepción? |
| Coherencia nutricional | ¿Las comidas propuestas tienen sentido culinario y nutricional conjunto? |
| Adecuación | ¿La energía/macros resultantes son razonables para el caso? |
| Factibilidad | ¿Un paciente real podría seguir este plan (disponibilidad, presupuesto, preparación)? |
| Claridad | ¿Las cantidades, unidades y recomendaciones son claras y accionables? |

No se implementa dashboard para esta rúbrica en el MVP: es un instrumento de
papel/formulario externo para quien ejecute el estudio.
