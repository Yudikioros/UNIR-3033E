# Fase 4: generación estructurada del borrador con LLM

No se tocan las fórmulas de Fase 3, ni BAM.xlsx, ni se agregan documentos
ficticios. El LLM organiza y propone; nunca calcula, nunca aprueba, nunca
inventa fuentes ni equivalencias SMAE.

## Flujo implementado

```
NutritionConsultation
  -> resultados determinísticos de Fase 3 (fuente de verdad; 409 si faltan)
  -> FoodDatabaseService (si está disponible; WARNING si no)
  -> KnowledgeBaseService / RAG (si hay fuentes autorizadas; WARNING si no)
  -> DietPlanGenerationContext (anonimizado)
  -> LLMClient.generate_structured (JSON estricto + Pydantic)
  -> validaciones deterministas (PlanValidation)
  -> DietPlan DRAFT + DietPlanMeal + DietPlanFood + AIGeneration + RetrievedSource
```

## 1. Revisión previa (qué se reutilizó, qué es nuevo)

- `POST /api/v1/generate-draft` (legacy, `PatientIn`/`save_legacy_draft`): intacto,
  no forma parte de este flujo. Sigue siendo la ruta pre-Fase 1.
- `llm_client.py`: se agregó `LLMClient`/`LLMGenerationError` sin tocar
  `client`/`MODEL_NAME`/`generate_diet_plan_draft` (usados por la ruta legacy).
- `get_exact_macros()` (Fase 3.5): se reutiliza indirectamente vía
  `get_food_database_service().search()`.
- `KnowledgeBaseService.search()`/`RetrievedKnowledgeChunk` (Fase 3.5): se
  consumen tal cual, sin cambios.
- `DietPlan`/`DietPlanMeal`/`DietPlanFood`/`AIGeneration`/`RetrievedSource`/
  `PlanValidation`/`GenerationPlanLink`/`PlanNutrientObservation` (Fase 1): ya
  existían en el schema; `plan_read()` (Fase 1) ya sabía proyectarlos. No se
  agregó ninguna tabla ni migración nueva en esta fase.
- Frontend: el botón "Generar borrador" existía deshabilitado; se conectó sin
  rediseñar el layout de dos paneles.

## 2. Resolución de la deuda de Fase 3.5 (slug → UUID)

`repositories/knowledge.py::resolve_source_id(db, manifest_source_id)`:
busca el slug en el manifiesto actual, obtiene su `file`, y resuelve el
`KnowledgeSource.id` real buscando por `originalFilename`. Si el slug no
está en el manifiesto, o está pero nunca se sincronizó a base de datos,
devuelve `None` — nunca inventa ni adivina un id. `generate_draft` usa esto
para cada `RetrievedKnowledgeChunk`: si no resuelve, esa fuente simplemente
no se persiste en `RetrievedSource` (no hay entrada "fantasma").
No se implementó desactivación automática de fuentes retiradas del
manifiesto (explícitamente no obligatorio en esta fase).

## 3. Contexto anonimizado

`schemas/generation.py::DietPlanGenerationContext` (`extra='forbid'`): edad,
sexo, peso/talla opcionales, actividad, objetivo, comidas/día, presupuesto,
preferencias/restricciones/alergias, notas nutricionales, y los 6 resultados
de Fase 3 (targetCalories, proteinGrams, carbohydrateGrams, fatGrams,
fiberGrams, waterLiters). No incluye `name`, `id`, `patientId`, `email`,
`phone` ni `birthDate` — estructuralmente no existen como campos del modelo.
Prueba dedicada (`test_build_context_no_filtra_pii_del_paciente`) construye
una consulta ficticia con esos datos reales y confirma que ninguno aparece
en el contexto ni en el prompt final.

## 4. Datos calculados como restricciones (no como sugerencia)

El prompt de usuario incluye textualmente:
`Target energy: X kcal / Protein: X g / Carbohydrates: X g / Fat: X g /
Fiber target: X g / Water target: X L`, con la instrucción explícita "Estos
valores YA fueron calculados... No los recalcules ni los cambies". El system
prompt refuerza "NO DEBES: Recalcular ni modificar la energía objetivo ni
los macronutrientes".

## 5. Proveedor LLM

`services/llm_client.py::LLMClient` — envoltorio genérico sobre
`AsyncOpenAI`, reutiliza `LLM_API_URL`/`LLM_MODEL` (Ollama por defecto). No
guarda API keys reales (`api_key="EMPTY"`, igual que la ruta legacy).
Configuración centralizada por variables de entorno:

- `ALIMENTIA_LLM_TEMPERATURE` (default `0.2`)
- `ALIMENTIA_LLM_TIMEOUT_SECONDS` (default `240`; ajustado tras medir 110-235s
  de respuesta real con Ollama/llama3.2:3b en CPU — ver sección 12)
- `ALIMENTIA_RAG_TOP_K` (default `3`)

`generate_structured()` intenta `response_format={"type":"json_object"}` y
reintenta sin ese parámetro si el backend no lo soporta; extrae el JSON
(quitando cercas de markdown, igual que la ruta legacy) y lo valida contra
el modelo Pydantic solicitado. Nunca usa regex para interpretar el plan.

## 6. Prompt versionado

`DIET_PLAN_PROMPT_VERSION = "1.0"` centralizado en
`services/diet_plan_generation.py`; se registra en `AIGeneration.promptVersion`
en cada intento (éxito o fallo).

## 7. Salida estructurada / JSON schema

`schemas/generation.py`: `GeneratedFood` (foodName, quantity>0, unit,
calorías/proteína/carbohidratos/grasa nullable, notes) → `GeneratedMeal`
(mealType, name, foods) → `GeneratedDietPlan` (summary, meals, recommendations).
Deliberadamente **sin** `smaeEquivalent` ni ningún campo de fuente
bibliográfica: el LLM no puede declarar ninguno porque el schema no se lo
permite (`extra='forbid'`). El `smaeEquivalent` de cada `DietPlanFood` se
fija en `null` al persistir — nunca lo decide el modelo.

## 8. Validaciones deterministas (post-generación)

`run_validations()` en `diet_plan_generation.py`, persistidas en
`PlanValidation`:

| Código | Severidad | Bloqueante |
|---|---|---|
| `MEAL_COUNT_MISMATCH` | WARNING | No |
| `RESTRICTED_FOOD_FOUND` | ERROR | Sí |
| `ENERGY_WITHIN_TOLERANCE` (±5%) | INFO | No |
| `ENERGY_OUT_OF_TOLERANCE` | WARNING | No |
| `INCOMPLETE_NUTRITION_DATA` | INFO | No |
| `FOOD_DATABASE_UNAVAILABLE` | WARNING | No |
| `KNOWLEDGE_BASE_UNAVAILABLE` | WARNING | No |

Ninguna validación bloqueante impide la creación del `DietPlan DRAFT` en esta
fase (no hay flujo de aprobación todavía); `isBlocking` queda registrado
para cuando exista.

## 9. Endpoint

`POST /api/v1/consultations/{consultation_id}/generate-draft` (mismo router
y manejo de errores que `capture.py`/`/calculate`). Precondiciones:
404 (consulta inexistente) → 422 (incompleta/fuera de alcance, mismo
`readiness()` de Fase 2/3) → 409 (`"Los requerimientos nutricionales deben
calcularse antes de generar el borrador."` si falta el cálculo) → 502
(`"No fue posible generar el borrador. Intenta nuevamente."` si el LLM
falla o responde JSON inválido). Éxito: `200` con `generationId`,
`dietPlanId`, `version`, `status`, `plan` completo, `validations`, `sources`,
`foodDatabaseUsed`, `knowledgeBaseUsed`.

## 10. Persistencia

Una generación exitosa crea, en una sola transacción: `AIGeneration`
(status `SUCCESS`), `DietPlan` (status `DRAFT`, `version` = conteo previo + 1,
nunca sobrescribe), `DietPlanMeal`/`DietPlanFood` normalizados,
`GenerationPlanLink` (`isOrigin=true`), `PlanValidation` por cada hallazgo,
`PlanNutrientObservation` (totales solo si *todos* los alimentos traen ese
dato) y `RetrievedSource` solo para fuentes con `sourceId` resuelto a un
`KnowledgeSource` real. Una generación fallida crea únicamente `AIGeneration`
(status `FAILED`, `errorMessage`); nunca crea un `DietPlan` a medias.

## 11. Frontend

`components/capture/diet-plan-draft.tsx` (nuevo) reemplaza el botón
deshabilitado "Generar borrador · Pendiente". Estados reales (sin delays
simulados): botón deshabilitado hasta que existe cálculo; `"Generando
borrador…"` durante la solicitud; al resolver, muestra el banner **BORRADOR
· Pendiente de revisión profesional** (nunca "aprobado"), las comidas/
alimentos generados, las validaciones con su severidad, y las fuentes reales
o `"Ninguna fuente documental configurada."` con el aviso correspondiente
si RAG/BAM no están configurados.

## 12. Validación en Docker

- Build + migración: sin migraciones nuevas ("No pending migrations to
  apply"); 4 pacientes y 3 planes preservados en cada reconstrucción.
- **141/141 pruebas** aprobadas (110 previas + 31 nuevas), con el LLM
  mockeado (`FakeLLMClient` inyectado vía `llm_client=`).
- `npm run build` y `npm run lint` sin errores.

### Integración real con Ollama (`llama3.2:3b`, descargado para esta verificación)

Sobre la consulta demo real de María González (`6b32a5d9-...`, targetCalories
1685.89 recuperado de la consulta persistida, no hardcodeado):

- **Primeros 4 intentos**: el modelo respondió, pero devolvió `quantity` como
  texto combinado con la unidad (`"1 taza"`, `"100g"`, `"1/2"`) en vez de un
  número puro. La validación estructural (Pydantic) rechazó correctamente
  cada respuesta; se registró `AIGeneration(status=FAILED, errorMessage=...)`
  con el detalle exacto; **no se creó ningún `DietPlan`** — comportamiento
  correcto de la sección 17. El endpoint devolvió `502` con el mensaje
  esperado, sin exponer el traceback al usuario.
- Se reforzó el prompt (mismo `DIET_PLAN_PROMPT_VERSION = "1.0"`, antes de
  considerarlo finalizado) con una regla explícita y ejemplos correcto/incorrecto
  para el campo `quantity`.
- **5.º intento, exitoso** (`200 OK` en 112.7s): creó
  `DietPlan` `6dc97de3-ab1d-44ea-a29a-fcbaa1038008`, versión 1, `status=DRAFT`.
  El modelo generó solo 1 comida (esperaba 5) con 150 kcal (objetivo 1685.89
  kcal) — limitaciones reales de un modelo de 3B en CPU, no un fallo del
  sistema. Las validaciones deterministas lo reflejaron correctamente:
  `MEAL_COUNT_MISMATCH` (WARNING), `ENERGY_OUT_OF_TOLERANCE` -91.1% (WARNING),
  `FOOD_DATABASE_UNAVAILABLE` y `KNOWLEDGE_BASE_UNAVAILABLE` (WARNING, reflejan
  el estado real: sin BAM ni documentos). `smaeEquivalent: null` en los 3
  alimentos generados; `sources: []`. Ninguna validación bloqueante impidió
  la persistencia del DRAFT — correcto, no hay flujo de aprobación todavía.
- **Hallazgo operativo**: el timeout por defecto anterior (120s) era
  insuficiente para este proveedor/modelo/hardware (respuestas reales de
  110-235s); un timeout corto no solo falla, sino que dispara el fallback
  sin `response_format`, dejando la generación anterior corriendo del lado
  del servidor sin cancelarla — con reintentos repetidos esto apila tareas
  huérfanas en Ollama y degrada aún más el tiempo de respuesta. Se corrigió
  el default a `240s` en `llm_client.py`, `.env.example` y `docker-compose.yml`
  (sección 5), basado en esta medición real, no en una suposición.
- Verificado después de cada intento: `GET /api/v1/patients` (4),
  `GET /api/v1/plans` (subió de 3 a 4 tras el único éxito, correctamente — no
  hubo planes fantasma de los 4 intentos fallidos), `GET /api/v1/resources/status`
  sin cambios.

## 13. Deuda técnica explícita

- `KnowledgeBaseService.search()` instancia un `HuggingFaceEmbedding` nuevo
  en cada llamada (igual patrón que la ruta legacy `get_clinical_retriever`);
  no se cachea entre solicitudes. No es incorrecto, pero es una oportunidad
  de rendimiento para una fase posterior.
- Un cliente que se desconecta antes de que el LLM responda no cancela la
  generación del lado del servidor (FastAPI/Starlette no lo hace por
  defecto); si el proveedor es lento, una serie de reintentos del cliente
  puede apilar solicitudes huérfanas en el proveedor (ver hallazgo real
  arriba). Mitigado subiendo el timeout por defecto; una solución más
  completa (cancelación explícita, límite de concurrencia por consulta)
  queda para una fase posterior si el proveedor real lo amerita.
- Un modelo pequeño (3B) en CPU no garantiza cumplir `mealsPerDay` ni
  acercarse al objetivo calórico en un intento; el sistema lo detecta y lo
  reporta (no lo oculta), pero no reintenta automáticamente ni mejora el
  borrador — queda a criterio del nutriólogo pedir uno nuevo.
- No existe todavía un endpoint para recuperar un `DietPlan` ya generado sin
  volver a generarlo (`GET /api/v1/plans/{id}` no existe); el frontend
  muestra el resultado en memoria justo después de generarlo. Si el usuario
  recarga la página, debe generar de nuevo para volver a verlo (no se pierde
  el historial en base de datos, solo la vista inmediata).
- `sync_knowledge_sources` no desactiva fuentes retiradas del manifiesto
  (heredado de Fase 3.5, explícitamente no obligatorio aquí).
- No se implementó aprobación/rechazo, edición manual del plan, exportación,
  ni comparación de versiones — quedan para fases posteriores según el plan.
