# Fase 1: modelos y persistencia

Se conserva Prisma Client Python y SQLite. No se implementan nuevas funciones de
LLM, RAG, edición, regeneración, aprobación o rechazo, ni cambios de interfaz.

## Modelos

`Patient` conserva sus IDs y `sex` se mapea a la columna `gender` existente.
La ampliación inicial fue normalizada por la tercera migración: preferencias,
condiciones, cálculos y vínculos de generación tienen relaciones separadas.
Los atributos históricos y JSON exactos se conservan en snapshots inmutables.
La justificación de claves y dependencias está en [NORMALIZATION_3NF.md](NORMALIZATION_3NF.md).

Se agregan `NutritionConsultation`, `DietPlanMeal`, `DietPlanFood`, `AIGeneration`,
`KnowledgeSource`, `RetrievedSource`, `PlanValidation` y `DietPlanChangeLog`.
Las consultas tienen medidas y resultados históricos. Las versiones de plan tienen
restricción única `(consultationId, version)` y versión positiva. Las relaciones
usan eliminación restringida, índices de consulta y comprobaciones que evitan
mezclar pacientes/consultas/generaciones.

SQLite con este cliente usa strings en lugar de enums Prisma: los estados y
severidades tienen enums Python y restricciones SQL CHECK. Los triggers y CHECK
forman parte de la migración; NO usar `prisma db push` para actualizar este esquema.
Revisar su conservación en las futuras migraciones que reconstruyan tablas.

## Migración

1. `202609050001_legacy_baseline`: representa exactamente las dos tablas antiguas.
2. `202609050002_phase1_persistence`: ampliación controlada y conversión histórica.
3. `202609050003_third_normal_form`: descomposición normalizada con preservación histórica.

`migrate.py` utiliza la API de backup SQLite, valida integridad, rechaza esquemas
antiguos desconocidos y estados sin mapeo, establece la baseline cuando corresponde,
ejecuta `prisma migrate deploy` y verifica los registros originales campo a campo.
Los cambios de tablas y datos de las migraciones segunda y tercera están en transacciones.
El inicio Docker utiliza este script y no `db push`.

Cada plan previo recibe una consulta `legacy-consultation-<id-plan>`. Se conserva
la fecha del plan como fecha histórica y el TDEE registrado. No se inventan peso,
talla, edad de la consulta, método, autor o fecha de aprobación. Los campos faltantes
son nullable. Las creaciones nuevas tienen contratos más estrictos que las lecturas
históricas.

La migración recupera comidas y alimentos del JSON cuando tienen estructura legible.
Una cantidad explícita como `1 taza` se convierte a `quantity=1`, `unit=taza`, sin
convertirla a gramos. Los formatos ambiguos quedan nullable. Siempre se conserva
el JSON exacto y `legacyQuantity`. Los nutrientes se recuperan solo si son numéricos;
no se calculan totales ni equivalencias en esta fase.

Estados: BORRADOR → DRAFT; EN REVISIÓN → UNDER_REVIEW; MODIFICADO → MODIFIED;
REGENERADO → REGENERATED; RECHAZADO → REJECTED; PLAN APROBADO → APPROVED.
Los estados canónicos existentes también se aceptan. No se fabrican datos de
aprobación para registros que ya venían aprobados.

## Seed

`seed.py` crea un caso separado con `demoKey=phase1-maria-mvp` y una consulta con
`demoKey=phase1-maria-mvp-consultation`. La clave única hace el seed idempotente;
no se identifica ni sobrescribe a una persona por su nombre. La María histórica
con patología queda intacta. El nuevo caso tiene 28 años, sexo femenino, 68 kg,
1.65 m, actividad moderada, pérdida de peso, 5 comidas y presupuesto mínimo/máximo
120/160 MXN. `dailyBudget` queda null porque se proporcionó un rango. No se crea
un plan ficticiamente generado/aprobado ni se añade una fuente ficticia al seed.

## Contratos y compatibilidad

`src/app/schemas/persistence.py` contiene PatientCreate/Update/Read,
NutritionConsultationCreate/Read, DietPlanRead, comidas/alimentos y enums.
Las preferencias se almacenan como filas individuales. El adaptador conserva
el contrato textual anterior mediante proyecciones. `repositories/normalized.py`
prepara creaciones y lecturas sobre las nuevas relaciones.

`repositories/legacy.py` concentra las consultas existentes y el guardado transaccional
necesario para mantener la ruta antigua. Devuelve `gender` y etiquetas de estado
compatibles con las páginas actuales. La BD utiliza estados canónicos. La ruta
antigua sigue creando un paciente por generación; se corregirá en la fase del
flujo paciente-consulta, no en esta fase de persistencia.

Los payloads de AIGeneration son opcionales, sin captura automática. La retención
está desactivada por defecto; un CHECK impide guardar payloads si no se habilita
explícitamente. No hay campos de credenciales ni secretos en modelos/seed/tests.
La futura capa LLM deberá anonimizar y depurar payloads antes de habilitar su
retención: una columna de texto no puede garantizar que su contenido sea anónimo.

## Operación y pruebas

Desde `alimentia/`, con Docker iniciado:

```powershell
docker compose build backend
docker compose up -d --no-deps backend
docker compose exec -T backend uv run --no-sync python seed.py
docker compose exec -T backend uv run --no-sync prisma validate
docker compose exec -T backend uv run --no-sync prisma migrate status
docker compose exec -T backend uv run --no-sync python -m unittest discover -s tests -v
```

Las pruebas de integración crean bases temporales, aplican el SQL de migraciones
y usan clientes Prisma reales. No usan la base local. Cubren relaciones, versiones,
unicidad, reconexión, fuentes recuperadas, auditoría, enums, retención de payloads,
compatibilidad, preservación histórica y seed repetido. No ejecutan cálculos ni LLM.

Para ensayar la migración sobre una copia se puede ejecutar:
`uv run --no-sync python migrate.py --database /ruta/a/copia.db`.
No ejecutar migraciones mientras haya escrituras concurrentes de la aplicación.
La aplicación arranca solo después de migrar correctamente.

## Recuperación

Los backups se guardan junto a SQLite y no se eliminan automáticamente. Para
restaurar: detener backend, conservar una copia del estado fallido, restaurar el
backup completo mediante SQLite backup o copia con conexiones cerradas y arrancar
la versión de código compatible. No ejecutar reset ni borrar la base actual.
La reversión es por backup completo, no por una migración inversa que descarte datos.

## Deuda explícita para fases siguientes

- Identidad del profesional: approvedBy/rejectedBy/changedBy están preparados como
  texto; no representan todavía una sesión autenticada ni implementan aprobación.
- La ficha sigue usando MOCK_DB y los listados siguen usando su contrato antiguo.
- Los datos históricos incompletos deben completarse en consultas nuevas.
- La falta de PDFs/BAM y del modelo Ollama se mantiene como situación previa.
- Los CHECK/triggers SQLite requieren revisión al generar migraciones futuras.
- Este despliegue local no incorpora control de acceso nuevo ni anonimización LLM.

## Verificación local del 5 de septiembre de 2026

- Backup inicial: `alimentia/data/db/alimentia-before-phase1-20260905-192423.db`.
- Backup automático previo al deploy: `alimentia/data/db/alimentia-backup-20260905T194310334551.db`.
- Imagen anterior conservada como `alimentia-backend:pre-phase1`.
- Migración ensayada sobre copia del backup y repetida sin pendientes.
- Migración local aplicada y confirmada por `prisma migrate status`.
- Comparación SQL con el backup: los 3 pacientes y los 3 planes originales,
  sus IDs, campos históricos y JSON siguen presentes.
- Resultado: 4 pacientes, 4 consultas, 3 planes, 1 comida, 1 alimento;
  ninguna generación IA ni fuente ficticia añadida.
- Seed ejecutado dos veces con los mismos IDs de paciente y consulta.
- Caso MVP: paciente `a61b04cc-56cb-4851-bedb-b2ad0c78e07a`, consulta
  `6b32a5d9-73e8-44c9-8569-90eb613a813f`.
- 23 pruebas aprobadas en contenedor aislado y nuevamente en el backend desplegado.
- `PRAGMA integrity_check`: ok; `PRAGMA foreign_key_check`: sin violaciones.
- Incidencias resueltas: BOM de PowerShell en migration_lock.toml (P3019),
  cierre explícito de conexiones SQLite en scripts y tests.
- Hashes de llm_client.py, rag_engine.py, calculator.py y food_db.py idénticos
  a los de la imagen anterior. No se modificó el frontend.
- Backend reiniciado: `/health`, `/api/v1/patients` y `/api/v1/plans` respondieron
  correctamente, con los mismos IDs de 4 pacientes y 3 planes antes y después.
- Validación final de Prisma y compilación de todos los módulos Python: correctas.
