# Fase 3: motor de cálculo nutricional determinístico

No se modifican modelos, migraciones, LLM, RAG ni BAM.xlsx. El schema de la
Fase 1 (`ConsultationCalculation`, `CalculationMetric`) ya anticipaba esta
fase y se reutiliza sin cambios de esquema.

## Motor

`src/app/services/calculator.py` agrega `NutritionCalculationService`
(instancia `nutrition_calculation_service`) sin tocar las funciones heredadas
`calculate_bmr`/`calculate_tdee`/`get_nutritional_baseline` que sigue usando
`POST /api/v1/generate-draft` (texto libre, no los enums de consulta).

Fórmulas y constantes centralizadas en el mismo módulo:

- IMC = peso_kg / talla_m².
- BMR: Mifflin-St Jeor (`MIFFLIN_ST_JEOR`, `RULE_VERSION = "1.0"`).
- TDEE = BMR × `ACTIVITY_FACTORS[activityLevel]` (sedentary 1.20, light 1.375,
  moderate 1.55, active 1.725, very active 1.90; mapeados sobre el enum
  `ActivityLevel` existente, sin duplicarlo).
- Energía objetivo = TDEE + `GOAL_ADJUSTMENTS_KCAL[goal]` (WEIGHT_LOSS -500,
  MAINTENANCE 0, WEIGHT_GAIN +300); rechaza resultados <= 0 kcal.
- Macros: distribución fija 25/45/30 % (proteína/carbohidrato/grasa),
  4/4/9 kcal por gramo.
- Fibra: 14 g / 1000 kcal objetivo. Agua: 35 ml/kg de peso.
- `validate_calculation_inputs` valida rangos técnicos de captura (no
  clínicos): edad 18-100, peso 20-350 kg, talla 1.20-2.30 m, además de sexo/
  actividad/objetivo reconocidos. Lanza `NutritionCalculationError`.

El resultado es un diccionario con `metrics` (9 valores), `details`
(fórmula, factores, ajuste de meta, distribución de macros, reglas de fibra/
agua; reconstruye el cálculo) y `calculationMethod`/`calculationRuleVersion`/
`calculatedAt`. La misma entrada produce siempre la misma salida.

## Persistencia

`repositories/capture.py::calculate_consultation` reutiliza `readiness()`
(Fase 2) para exigir los mismos datos mínimos que "consulta lista", y agrega
un registro nuevo a `ConsultationCalculation` + 9 `CalculationMetric` por
llamada — nunca sobrescribe: cada cálculo (incluido un recálculo) queda en el
historial. `consultation_read()` (Fase 1) ya proyectaba el cálculo más
reciente sobre `NutritionConsultationRead`; no se tocó.

`calculatedAt` no tiene columna propia en el contrato de lectura, así que se
incluye dentro de `calculationDetails` (JSON) para trazabilidad, junto con
`calculationMethod`/`calculationRuleVersion` que sí son campos de primera
clase.

Errores: 404 consulta inexistente; 422 datos incompletos (mismo criterio que
"lista"); 400 datos técnicamente fuera de rango o energía objetivo <= 0; 500
solo ante fallos inesperados reales. Calcular no exige que la consulta sea
editable: un recálculo es válido aunque ya exista un plan o generación.

## API

`POST /api/v1/consultations/{consultation_id}/calculate` (mismo router y
manejo de errores que `capture.py`): recupera la consulta, valida, calcula,
persiste y devuelve el `ConsultationDetail` actualizado.

## Frontend

Nueva sección "Requerimientos nutricionales" en la ficha del paciente
(`components/capture/nutrition-requirements.tsx`), entre "Datos de la
consulta actual" y "Plan dietético". Muestra IMC/BMR/TDEE/objetivo/macros/
fibra/agua reales cuando existen, "Cálculo pendiente" en caso contrario, y un
botón Calcular/Recalcular deshabilitado si la consulta tiene
`readinessIssues`. Incluye el aviso "Calculado mediante reglas · Método:
Mifflin-St Jeor" para dejar explícito que no proviene de IA generativa.

Se actualizó el texto obsoleto "Los cálculos se habilitarán en la siguiente
fase" en `consultation-form.tsx` y "Cálculos y generación del plan
pendientes..." en la tarjeta de Plan dietético (ahora solo la generación
sigue pendiente). No se tocó ningún otro mock: `alerts/page.tsx` y
`sources/page.tsx` siguen fuera del alcance de esta fase.

## Pruebas

`tests/test_calculator.py` (23): Mifflin hombre/mujer, IMC, actividad
sedentaria/moderada, pérdida/mantenimiento/incremento, macros, fibra, agua,
6 validaciones de entrada inválida, reproducibilidad y el caso María
González (edad 28, femenino, 68 kg, 1.65 m, moderada, pérdida de peso) con
valores esperados calculados en la prueba misma, no hardcodeados.

`tests/test_calculate_endpoint.py` (7): consulta inexistente (404), consulta
incompleta (422), consulta válida (200, persistido y recuperable por GET),
recálculo (agrega historial, no sobrescribe), no crea paciente/consulta
nuevos, datos fuera de rango técnico (400), y el caso demo real via
`seed.py` (María González, `demoKey=phase1-maria-mvp-consultation`).

## Verificación local — 6 de septiembre de 2026

- Backup automático de despliegue: `../data/db/alimentia-backup-20260906T220639368671.db`.
- Sin migraciones nuevas: "No pending migrations to apply"; datos previos
  intactos (4 pacientes, 3 planes).
- 87 pruebas backend aprobadas (57 de fases previas + 23 + 7 de esta fase).
- Backend arrancó sin PDFs ni BAM.xlsx (WARNING, sin stack trace), igual que
  antes de esta fase.
- Se calculó la consulta demo real (`a61b04cc-...` /
  `6b32a5d9-73e8-44c9-8569-90eb613a813f`, María González, 28 años, femenino,
  68 kg, 1.65 m, actividad moderada, pérdida de peso) vía
  `POST /api/v1/consultations/{id}/calculate`: IMC 25.0, BMR 1410.25 kcal,
  TDEE 2185.89 kcal, objetivo 1685.89 kcal, proteína 105.4 g, carbohidratos
  189.7 g, grasa 56.2 g, fibra 23.6 g, agua 2.38 L. Persistido y confirmado
  con una lectura GET posterior. `isEditable` pasó a `false` (mismo criterio
  de Fase 2 para consultas con resultados registrados).
- `GET /api/v1/patients` (4) y `GET /api/v1/plans` (3) sin cambios tras el
  cálculo.
- Frontend: `npm run build` y `npm run lint` sin errores.

## Deuda explícita para fases siguientes

- El desempate de "cálculo más reciente" en `consultation_read()` usa
  `(recordedAt, id)`; en SQLite con timestamps empatados al segundo esto
  podría, en teoría, no favorecer el último cálculo por orden de creación.
  No se tocó: es lógica de Fase 1 y los timestamps observados tienen
  precisión de microsegundos.
- Los rangos técnicos (edad/peso/talla) y la distribución de macros/fibra/
  agua son reglas explícitas del MVP, no clínicas; quedan centralizadas en
  `calculator.py` para configurarse más adelante sin dispersarse.
- Generación de plan dietético, LLM y RAG siguen sin implementarse
  (fuera de alcance de esta fase).
