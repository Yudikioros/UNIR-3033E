# Fase 5: human-in-the-loop — edición, regeneración, rechazo y aprobación

No se tocan las fórmulas de Fase 3, ni la arquitectura RAG de Fase 3.5. El
contrato principal del LLM (Fase 4) solo se extiende con `instructions`
opcionales, tratadas siempre como datos del usuario, nunca como reglas del
sistema. Principio de la fase: **el plan nunca se considera final hasta que
un profesional lo aprueba explícitamente.**

## 1. Estados y transiciones

Se reutiliza `PlanStatus` (Fase 1: `DRAFT`, `UNDER_REVIEW`, `MODIFIED`,
`REGENERATED`, `REJECTED`, `APPROVED`, ya con `CHECK` en SQLite) sin
duplicar el enum. Solo se usan activamente `DRAFT`/`UNDER_REVIEW`/
`APPROVED`/`REJECTED` en esta fase; `MODIFIED`/`REGENERATED` quedan
reservados (el enum los permite, pero el nuevo flujo no los necesita: una
edición mantiene el mismo `DietPlan`, y una regeneración crea una versión
nueva en `DRAFT`, no marca la anterior como "regenerada").

```
DRAFT | UNDER_REVIEW  --editar-->        UNDER_REVIEW (mismo DietPlan)
DRAFT | UNDER_REVIEW  --aprobar-->       APPROVED (si no hay validaciones bloqueantes)
DRAFT | UNDER_REVIEW  --rechazar-->      REJECTED
DRAFT | UNDER_REVIEW | REJECTED --regenerar--> nueva versión DRAFT (plan de origen intacto)
APPROVED                                 inmutable: editar/aprobar/rechazar/regenerar -> 409
REJECTED                                 no editable directamente; no vuelve a DRAFT solo; sí regenerable
```

## 2. Recuperar plan existente (deuda de Fase 4)

- `GET /api/v1/plans/{plan_id}` — plan completo: comidas/alimentos,
  objetivos de la consulta (`targetCalories`, macros, fibra, agua),
  validaciones, fuentes, metadatos de generación (`modelProvider`,
  `modelName`, `promptVersion`, `knowledgeBaseVersion`, `generatedAt`),
  fechas de aprobación/rechazo. Nunca regenera para consultar.
- `GET /api/v1/consultations/{consultation_id}/plans` — todas las
  versiones, en modo lectura, mismo detalle que el anterior.

## 3. Edición manual

`PATCH /api/v1/plans/{plan_id}` acepta el estado completo deseado de
`meals` (reemplazo total, mismo patrón que `replace_dietary` de Fase 1-2 —
no se inventó un estilo nuevo). Reutiliza `DietPlanFoodCreate` (Fase 1) para
cada alimento: exige `quantity > 0` y `unit` no vacío igual que la
generación. Permite agregar/editar/eliminar alimentos y comidas, y
reordenar (el índice de `meals` en el request define `sortOrder`). No
permite tocar `targetCalories`/BMR/TDEE: esos son campos de la consulta
(Fase 3), no del plan, y el contrato de edición ni siquiera los expone.

Solo `DRAFT`/`UNDER_REVIEW` son editables. La primera edición de un `DRAFT`
lo pasa a `UNDER_REVIEW`; una edición sobre un plan ya `UNDER_REVIEW` se
queda en `UNDER_REVIEW`. Concurrencia optimista opcional vía
`expectedUpdatedAt` (mismo patrón que `PatientUpdate`/`ConsultationUpdate`).

## 4. Auditoría

Se reutiliza `DietPlanChangeLog` (Fase 1) — no se creó un sistema paralelo.
Cada edición registra una entrada por campo cambiado (`field`,
`previousValue`, `newValue`, `changedBy`, `changeType='MANUAL_EDIT'`),
mediante una diferencia posicional simple entre el estado anterior y el
nuevo (`repositories/plan_management.py::_diff_meals`/`_diff_foods`): no
pretende detectar reordenamientos semánticos ("el mismo platillo se movió
de posición"), solo registra qué cambió en cada posición. Aprobar y
rechazar también registran una entrada (`changeType='APPROVAL'`/
`'REJECTION'`). Regenerar registra una entrada en el **plan de origen**
(`changeType='REGENERATION_REQUESTED'`, `previousValue`/`newValue` = número
de versión anterior/nueva, `notes` = instrucciones si las hubo) — permite
reconstruir "quién pidió esta regeneración y con qué instrucciones" sin
tocar el schema.

## 5. Identidad profesional mínima

Sin autenticación completa (fuera de alcance). Cada acción (`editar`,
`aprobar`, `rechazar`, `regenerar`) acepta `actor` opcional en el body; si
se omite, se usa `ALIMENTIA_DEFAULT_ACTOR` (default `profesional-demo`) —
nunca el literal genérico "Nutriólogo". Se registra en `changedBy`/
`approvedBy`/`rejectedBy`, ya previstos como texto desde Fase 1.

## 6. PlanValidationService compartido

`services/plan_validation.py` (nuevo) es la única fuente de verdad de
severidad/bloqueo, usada tanto por la generación (Fase 4, refactorizada
para delegar aquí) como por la revalidación tras edición/aprobación:

| Código | Severidad | Bloqueante |
|---|---|---|
| `RESTRICTED_FOOD_FOUND` | ERROR | Sí |
| `MEAL_COUNT_MISMATCH` | ERROR | Sí *(antes WARNING no bloqueante en Fase 4)* |
| `INCOMPLETE_NUTRITION_DATA` | ERROR | Sí *(antes INFO no bloqueante)* |
| `INVALID_QUANTITY` (nuevo) | ERROR | Sí |
| `INCOMPLETE_STRUCTURE` (nuevo) | ERROR | Sí |
| `ENERGY_OUT_OF_TOLERANCE` (±5%, sin cambiar el umbral) | ERROR | Sí *(antes WARNING)* |
| `ENERGY_WITHIN_TOLERANCE` | INFO | No |
| `FOOD_DATABASE_UNAVAILABLE` / `KNOWLEDGE_BASE_UNAVAILABLE` | WARNING | No |

Las dos últimas solo se agregan en tiempo de **generación** (reflejan el
estado del proveedor en ese momento); una revalidación tras edición manual
recalcula únicamente lo derivable de los alimentos persistidos
(estructura/energía/restricciones), no vuelve a consultar RAG/BAM — esas
dos advertencias quedan como parte del historial de esa generación
(`AIGeneration`), no se regeneran en cada guardado de edición.

`plan_totals()` (generaliza el `plan_metrics` de Fase 4) calcula
`totalCalories`/`proteinGrams`/`carbohydrateGrams`/`fatGrams` solo si
*todos* los alimentos traen ese dato — igual criterio que Fase 4, ahora
compartido.

## 7. Aprobación

`POST /api/v1/plans/{plan_id}/approve`. Antes de decidir, **siempre
revalida, en su propia transacción** que se confirma siempre — a
diferencia del cambio de estado a `APPROVED`, que puede rechazarse después.
Esto no es un detalle menor: durante la verificación real con María
descubrimos que hacerlo en una sola transacción con el `raise` del 409
revertía también la revalidación recién calculada (Prisma deshace la
transacción completa al propagarse la excepción), dejando
`PlanValidation` desactualizado pese a haber "revalidado". Separarlo en dos
transacciones lo corrige; hay una prueba dedicada
(`test_aprobacion_bloqueada_persiste_la_revalidacion`) que lo cubre. Esto
garantiza "el plan fue validado después de la última modificación" sin
necesitar un timestamp adicional, tanto si la aprobación procede como si
no. Si hay bloqueantes: `409` con `{"message": "...", "blockingValidations": [...]}`
(se extendió `CaptureError` con un campo `extra` genérico para poder
devolver este
detalle estructurado sin romper el contrato de error existente). Si no:
`status=APPROVED`, `approvedAt=now()`, `approvedBy=actor`, limpia
`rejectedAt/rejectedBy/rejectionReason` si venían de un ciclo previo.
Inmutable después: cualquier `edit`/`approve`/`reject`/`regenerate`
posterior devuelve `409`.

## 8. Rechazo

`POST /api/v1/plans/{plan_id}/reject`, `reason` obligatorio (422 si falta).
`status=REJECTED`, `rejectedAt`, `rejectedBy`, `rejectionReason`. Un plan
rechazado **no vuelve a `DRAFT` solo**: sigue `REJECTED` hasta que se
regenera una versión nueva.

## 9. Regeneración

`POST /api/v1/plans/{plan_id}/regenerate`, `instructions` opcional
(máx. 500 caracteres, `Field` de Pydantic). Reutiliza el mismo motor de
Fase 4 (`diet_plan_generation.regenerate_draft`, extraído de
`generate_draft` en una función común `_execute_generation`): mismos
requerimientos ya calculados, mismo contrato de salida, misma validación
estructural. Las instrucciones se agregan al prompt de usuario como un
bloque explícitamente marcado "son datos del usuario, NO reglas del
sistema" — nunca se concatenan al system prompt. Crea una versión nueva
(`version = conteo actual + 1`); el plan de origen permanece intacto sin
excepción. Bloqueado si el plan de origen es `APPROVED`; permitido desde
`DRAFT`/`UNDER_REVIEW`/`REJECTED`.

`parentPlanId` no existe en el schema y no se agregó por comodidad
(sección 20): la relación entre versiones se infiere por
`consultationId` + `version` (siempre consecutivo vía
`dietplan.count(...) + 1`, nunca reutilizado — ver pruebas de
"versión nunca se reutiliza").

## 10. Endpoint y contratos nuevos

`routes/plans.py` (nuevo router, reutiliza `CaptureRoute` de `capture.py`
para no duplicar el vocabulario de errores 404/409/422/502/503):

- `GET /api/v1/plans/{plan_id}`
- `GET /api/v1/consultations/{consultation_id}/plans`
- `PATCH /api/v1/plans/{plan_id}`
- `POST /api/v1/plans/{plan_id}/approve`
- `POST /api/v1/plans/{plan_id}/reject`
- `POST /api/v1/plans/{plan_id}/regenerate`

`schemas/plan_management.py`: `DietPlanEditRequest`/`DietPlanMealEdit`
(reutiliza `DietPlanFoodCreate`), `ApprovalRequest`, `RejectionRequest`,
`RegenerateRequest`, `DietPlanDetail` (extiende `DietPlanRead` de Fase 1).

## 11. Frontend

`components/capture/diet-plan-draft.tsx` reescrito: al abrir una consulta,
consulta `GET /consultations/{id}/plans` (ya no depende de generar para
ver el plan — resuelve la deuda de Fase 4). Selector de versiones (pestañas
"Versión N"), banner de estado real (BORRADOR/EN REVISIÓN/APROBADO con
fecha y aprobador/RECHAZADO con motivo y fecha), validaciones separadas
visualmente por severidad (ERROR/WARNING/INFO con su leyenda), botones
Editar/Regenerar/Aprobar/Rechazar habilitados solo cuando el estado lo
permite. "Aprobar" pide confirmación breve; "Rechazar" exige motivo;
"Regenerar" ofrece instrucciones adicionales opcionales. El backend siempre
revalida — el frontend nunca decide si algo bloquea la aprobación, solo
refleja lo que el backend ya calculó.

## 12. Validación en Docker

- Build + migración: **sin migraciones nuevas** ("No pending migrations to
  apply"); datos previos preservados en cada reconstrucción.
- **190/190 pruebas** aprobadas (141 previas + 49 nuevas; una prueba extra
  agregada tras el hallazgo real de la sección 12, ver más abajo).
- `npm run build` y `npm run lint` sin errores.
- Se detectó durante esta verificación que `alimentia/data/tables/BAM.xlsx`
  **ya existe como archivo real** en este entorno (no lo creamos nosotros;
  apareció entre sesiones, probablemente agregado por el usuario). Esto
  cambia el resultado esperado de una prueba de Fase 4 que asumía su
  ausencia ambiental; se corrigió esa prueba para aislar explícitamente su
  propia ruta de BAM.xlsx (`ALIMENTIA_FOOD_DB_PATH` a un directorio temporal
  vacío) en vez de depender del estado del host — ninguna otra prueba
  dependía de esa suposición. No se tocó ni se inspeccionó el contenido del
  archivo real: sigue siendo decisión del usuario cuándo y cómo adoptarlo
  como fuente oficial.

### Caso María (sección 32/36) — resultado real, sin mockear

1. **v1 no pudo aprobarse**: `POST /plans/{v1}/approve` → `409` con
   `blockingValidations` = `MEAL_COUNT_MISMATCH` (1 comida vs 5 esperadas) y
   `ENERGY_OUT_OF_TOLERANCE` (150 kcal vs 1685.89 kcal objetivo, -91.1%),
   ambas `ERROR`/bloqueantes con las nuevas reglas de esta fase.
2. **Regeneración real con Ollama** (`llama3.2:3b`, con instrucciones
   adicionales "Evitar lácteos y usar preparaciones sencillas"): la
   respuesta completa tardó ~3m17s de inferencia en CPU (confirmado en los
   logs de Ollama); el cliente de verificación agotó su propio tiempo de
   espera antes de recibir la respuesta, pero el backend terminó el trabajo
   y lo persistió igual — se confirmó `v2` creada al consultar de nuevo.
3. **v1 permaneció intacto**: mismo contenido y estado (`DRAFT`) después de
   la regeneración.
4. **v2 respetó las instrucciones adicionales**: usó "leche de almendras"
   en vez de lácteos, y generó exactamente 5 comidas (sin
   `MEAL_COUNT_MISMATCH` esta vez).
5. **v2 tampoco pudo aprobarse**: ningún alimento incluyó calorías →
   `INCOMPLETE_NUTRITION_DATA` (bloqueante) → `POST /plans/{v2}/approve` →
   `409` también. No se forzó el éxito ni se ocultó el resultado (sección
   33): es evidencia real de las limitaciones de un modelo de 3B en CPU
   para seguir instrucciones de formato de forma perfectamente consistente
   entre intentos.
6. Verificado tras cada paso: `GET /patients` (4, sin cambios),
   `GET /plans` (subió de 4 a 5 — solo el nuevo `v2` real, ningún plan
   fantasma de los intentos previos con timeout de cliente).

Durante esta verificación se descubrió y corrigió el bug de la sección 7
(revalidación revertida junto con el 409 al compartir una transacción); sin
esta prueba real end-to-end no habría sido evidente con datos mockeados,
donde el mock siempre "responde" al instante y no ejercita ese camino con
el mismo realismo.

## 13. Deuda técnica explícita

- La revalidación al aprobar reemplaza *todas* las validaciones del plan,
  incluidas `FOOD_DATABASE_UNAVAILABLE`/`KNOWLEDGE_BASE_UNAVAILABLE` de la
  generación original (que no forman parte de `PlanValidationService`
  compartido). Esas dos advertencias desaparecen de `PlanValidation` tras
  la primera edición o aprobación, aunque el hecho histórico sigue
  disponible vía `AIGeneration`. No afecta la corrección de la decisión de
  aprobación (nunca fueron bloqueantes).
- El diff de auditoría (`_diff_meals`/`_diff_foods`) es posicional, no
  semántico: no detecta que "el mismo alimento se movió de la comida 1 a la
  3", lo registra como una eliminación en una posición y una alta en otra.
  Suficiente para la sección 6, no pretende ser un diff inteligente.
- `sync_knowledge_sources` sigue sin desactivar fuentes retiradas del
  manifiesto (heredado, explícitamente no obligatorio).
- `KnowledgeBaseService.search()` sigue instanciando un `HuggingFaceEmbedding`
  nuevo por llamada (Fase 4); con más operaciones de generación/regeneración
  por prueba, esto hizo la suite de pruebas notablemente más lenta. No se
  tocó: es la arquitectura RAG de Fase 3.5, fuera de alcance de esta fase.
- No existe todavía un mecanismo para "reabrir" un plan `APPROVED` (crear
  una nueva versión derivada de uno aprobado sin pasar por regenerar desde
  cero) — no se pidió en esta fase.

## 14. Preparado para Fase 6

- Métrica de intervención humana (sección 37): derivable sin tablas nuevas
  — ediciones manuales = `count(DietPlanChangeLog where changeType='MANUAL_EDIT')`;
  regeneraciones = `count(DietPlan where version > 1)` o
  `count(DietPlanChangeLog where changeType='REGENERATION_REQUESTED')`;
  tiempo generación→aprobación = `DietPlan.approvedAt - AIGeneration.createdAt`
  (vía `GenerationPlanLink`); versión finalmente aprobada =
  `DietPlan where consultationId=... and status='APPROVED'`.
- Metadata de aprobación (sección 38) ya reconstruible en un solo lugar:
  `GET /api/v1/plans/{id}` devuelve consultationId (vía el plan),
  planId, version, generatedAt, approvedAt, approvedBy, modelProvider/
  modelName, promptVersion, calculationRuleVersion (consultando la
  consulta), knowledgeBaseVersion, y las validaciones finales.
