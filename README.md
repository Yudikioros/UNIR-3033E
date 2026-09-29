# AlimentIA

**Planes dietéticos asistidos por modelos de lenguaje bajo supervisión de profesionales de nutrición.**

AlimentIA es un MVP académico para capturar consultas nutricionales y preparar borradores de planes dietéticos. Combina cálculos determinísticos, una base alimentaria estructurada, recuperación de documentos autorizados (RAG) y generación estructurada con un modelo de lenguaje. El profesional revisa el resultado, lo edita si hace falta y decide si lo aprueba o rechaza.

> AlimentIA es una herramienta de apoyo y evaluación de un prototipo. No diagnostica, no sustituye el criterio profesional ni aprueba planes automáticamente. El alcance actual se limita a adultos sin patologías clínicas complejas.

## Arquitectura

```text
Paciente y consulta
	-> cálculo nutricional determinístico y versionado
	-> consulta opcional a BAM y recuperación opcional de fuentes autorizadas
	-> contexto anonimizado para Ollama y generación de plan estructurado
	-> validaciones determinísticas y borrador versionado
	-> revisión, edición, regeneración, aprobación o rechazo por un profesional
	-> exportación PDF disponible únicamente para planes aprobados
```

Responsabilidades principales:

- **API y dominio**: FastAPI expone la API REST bajo `/api/v1`. Los contratos se validan con Pydantic y la lógica se organiza en servicios y repositorios.
- **Persistencia**: Prisma Client Python y SQLite almacenan pacientes, consultas, cálculos, versiones de planes, generaciones, validaciones, fuentes recuperadas y auditoría de cambios. Las migraciones se aplican mediante `migrate.py` al iniciar el backend.
- **Cálculo**: el motor determinístico calcula los objetivos nutricionales antes de generar el borrador. El LLM no recalcula ni modifica esos valores.
- **Alimentos**: `FoodDatabaseService` adapta la BAM (Base de Alimentos de México) cuando el archivo está disponible. Esta fuente tabular está separada del RAG y su uso se registra explícitamente.
- **Conocimiento documental**: LlamaIndex y Qdrant recuperan fragmentos de documentos declarados en `alimentia/data/knowledge_base/manifest.json`. Solo se ingieren fuentes autorizadas por el manifiesto; la ausencia de documentos no se disimula y no impide el resto de la aplicación.
- **Generación**: Ollama sirve el modelo configurado mediante una API compatible con OpenAI. La salida JSON se valida con esquemas Pydantic antes de persistirse como borrador.
- **Interfaz**: Next.js presenta pacientes, consultas y el flujo de revisión de planes; consume la API del backend.

## Revisión profesional y trazabilidad

Los planes tienen versiones y estados de revisión. La aprobación vuelve a ejecutar las validaciones y se bloquea si existen hallazgos bloqueantes. Una aprobación es inmutable; una regeneración crea una nueva versión y conserva intacto el plan de origen. Las ediciones, aprobaciones, rechazos y solicitudes de regeneración quedan auditadas.

La API permite consultar la trazabilidad del cálculo, recursos utilizados, fuentes recuperadas, generación y acciones humanas, además de métricas automáticas por plan. La exportación PDF solo está disponible para planes aprobados. Las métricas experimentales, como satisfacción o calidad clínica evaluada por profesionales, requieren un estudio externo y no las calcula el sistema.

## Tecnologías

- **Backend**: Python 3.14, FastAPI, Pydantic, Prisma Client Python y SQLite.
- **IA y recuperación**: Ollama, API compatible con OpenAI, LlamaIndex, sentence-transformers y Qdrant.
- **Recursos**: BAM en Excel, documentos PDF autorizados y manifiesto de conocimiento JSON.
- **Frontend**: Next.js 16, React 19, TypeScript y Tailwind CSS 4.
- **Ejecución local**: Docker Compose; configuración opcional para asignar GPU NVIDIA a Ollama.

## Endpoints principales

La documentación interactiva de la API está en `/docs` cuando el backend está iniciado.

- `GET /health`: estado del backend.
- `GET /api/v1/resources/status` y `GET /api/v1/sources`: disponibilidad de recursos y fuentes registradas.
- `/api/v1/patients` y `/api/v1/patients/{id}/consultations`: gestión de pacientes y consultas.
- `POST /api/v1/consultations/{id}/calculate`: cálculo nutricional de la consulta.
- `POST /api/v1/consultations/{id}/generate-draft`: generación de un borrador a partir de una consulta calculada.
- `/api/v1/plans/{id}`: lectura y gestión del plan, con operaciones de edición, regeneración, aprobación y rechazo.
- `GET /api/v1/plans/{id}/traceability` y `GET /api/v1/plans/{id}/evaluation-metrics`: trazabilidad y métricas del plan.
- `GET /api/v1/plans/{id}/export/pdf`: exportación del plan aprobado.

## Recursos y límites conocidos

- BAM y documentos RAG son recursos independientes y opcionales. Los resultados informan si se utilizaron; no se inventan alimentos, datos nutrimentales, equivalencias ni fuentes.
- El SMAE no está disponible como catálogo estructurado ni existe validación automática de equivalencias; `smaeEquivalent` permanece sin valor verificado.
- La coincidencia entre alimentos generados y BAM es conservadora. Los nombres genéricos o cantidades en unidades caseras pueden requerir corrección profesional y hacer que un borrador tenga validaciones bloqueantes.
- Algunas reglas nutricionales son supuestos del MVP, no recomendaciones clínicas validadas. La matriz de reglas distingue las respaldadas por fuentes de los supuestos y umbrales técnicos.
- El MVP no incorpora autenticación completa. La identidad de quien actúa se registra con un identificador de texto configurable, no como una sesión autenticada.
- El rendimiento y la calidad de generación dependen del modelo y del hardware; en CPU la inferencia puede ser lenta.

## Ejecución local

Consulta [LOCAL_SETUP.md](LOCAL_SETUP.md) para los requisitos, configuración, inicio con Docker Compose y GPU NVIDIA, carga de datos de demostración, comprobaciones y solución de problemas. La guía también documenta las direcciones locales de la interfaz, la API, Qdrant y Ollama.

Los datos persistentes se guardan en `alimentia/data/` (SQLite, archivos de conocimiento y alimentos, almacenamiento de Qdrant y modelos de Ollama). Para cargar o restaurar los casos de demostración, sigue el procedimiento de la guía; el seed no genera planes aprobados ficticios.

## Documentación técnica

- [Fase 1: persistencia y modelos](alimentia/backend/docs/PHASE1.md)
- [Fase 2: pacientes y consultas](alimentia/backend/docs/PHASE2.md)
- [Fase 3.5: fuentes y arquitectura RAG](alimentia/backend/docs/PHASE3_5.md)
- [Fase 4: generación estructurada](alimentia/backend/docs/PHASE4.md)
- [Fase 5: revisión profesional](alimentia/backend/docs/PHASE5.md)
- [Fase 6: trazabilidad, métricas y exportación](alimentia/backend/docs/PHASE6.md)
- [Integración de recursos reales](alimentia/backend/docs/REAL_RESOURCES_INTEGRATION.md)
- [Protocolo de evaluación](alimentia/backend/docs/EVALUATION_PROTOCOL.md)

## Integrantes

- Esdras de la Torre Valdivia
- Adrián Lago Aponte
- Oscar Arturo López Córdova
