# Fase 2: pacientes y consultas

La migración `202609060001_patient_consultation_capture` añade de forma aditiva
el estado de captura de las consultas y recibos de solicitud idempotentes. No
reconstruye ni elimina tablas de la Fase 1.

## API

- `GET /api/v1/capture-options`: opciones y límites derivados de los contratos.
- `GET`, `POST`, `PATCH /api/v1/patients` y `/api/v1/patients/{uuid}`.
- `GET`, `POST /api/v1/patients/{uuid}/consultations`.
- `GET`, `PATCH /api/v1/consultations/{id}`.

Las altas aceptan `Idempotency-Key` UUID. Repetir una petición con la misma
clave y el mismo contenido devuelve el mismo recurso; reutilizarla con otros
datos devuelve `409`. La detección de posible duplicado sólo bloquea un nombre
igual junto con la misma fecha de nacimiento o correo. Un nombre por sí solo no
identifica clínicamente a una persona.

Las actualizaciones pueden incluir `expectedUpdatedAt`; un registro modificado
en otra sesión devuelve `409`, para evitar que un formulario sobrescriba datos
que no ha visto. Las listas dietéticas operativas se sustituyen en sus relaciones
normalizadas, no se guardan como JSON operativo.

`NutritionConsultation.status` admite `DRAFT` y `READY`. `READY` requiere edad
adulta, peso, talla, sexo, actividad, objetivo y número de comidas. Una consulta
con un plan, generación o resultados ya registrados queda protegida contra
edición. Una condición histórica no se copia a la consulta; muestra el aviso de
revisión profesional que corresponde al alcance del MVP.

## Configuración

El frontend obtiene el origen de la API de `NEXT_PUBLIC_API_URL`; ver
`frontend/.env.example`. Docker obtiene `CORS_ORIGINS` de entorno. Las opciones
de selectores y límites salen de `capture-options` y de esquemas Pydantic, sin
catálogos clínicos duplicados en React.

## Interfaz

Se eliminó `MOCK_DB` de la ficha. La ruta `/patients/[uuid]` carga paciente,
historial, opciones y consulta activa. Muestra carga, 404, errores amigables,
estado de guardado, protección contra doble envío y una advertencia de cambios
sin guardar. La ficha conserva el diseño de dos paneles y distingue datos
habituales del paciente de la observación histórica de cada consulta.

El resumen muestra el contador real de pacientes. Las métricas de planes que
aún pertenecen a fases posteriores se muestran como `—` y “Pendiente de
información”. Siguen existiendo datos simulados sólo en `alerts/page.tsx` y
`sources/page.tsx`, que no pertenecen al módulo de pacientes o consultas.

## Verificación local — 6 de septiembre de 2026

- Backup previo: `../data/db/alimentia-before-phase2-20260906T045943.db`.
- Backup automático de despliegue: `../data/db/alimentia-backup-20260906T184550099360.db`.
- Imagen previa: `alimentia-backend:pre-phase2`.
- Migración ensayada dos veces sobre copia del backup: conserva 4 pacientes y
  3 planes; la segunda ejecución no tuvo pendientes.
- 44 pruebas backend aprobadas: las 30 de Fase 1 y 14 de captura HTTP.
- TypeScript, ESLint y `next build` aprobados.
- Se abrió María González por UUID real; se verificó el listado de 4 pacientes,
  ficha, historial, apertura de consulta, guardado y restauración de una nota
  desde la interfaz sin errores de consola.
- Se creó la consulta demostrativa `03f56466-0418-44b0-a43a-fb4062148f8c` para
  María; el reintento devolvió el mismo UUID. Tras reiniciar el backend, el
  historial conservó sus dos IDs.

No se modificaron LLM, RAG, cálculo ni generación de planes. El arranque sigue
registrando el problema anterior cuando no existen PDFs/BAM.xlsx; no afecta los
endpoints de captura, pero debe resolverse al trabajar en el módulo RAG.
