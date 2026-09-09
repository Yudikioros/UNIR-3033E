# Fase 3.5: fuentes nutricionales y base de conocimiento oficial

No se toca el motor de cálculo (Fase 3), el LLM ni la generación de borradores.
BAM.xlsx sigue sin ser la fuente oficial del MVP; esta fase lo convierte en un
adaptador reemplazable, no en un requisito del dominio.

## 1. Tres responsabilidades separadas

| Tipo | Dónde vive | Depende de documentos/LLM |
|---|---|---|
| **A. Cálculo nutricional** | `services/calculator.py` (Fase 3) | No |
| **B. Base alimentaria estructurada** | `services/food_db.py` (`FoodDatabaseService`) | No — es tabular, no RAG |
| **C. Base documental RAG** | `services/rag_engine.py` + `services/knowledge_manifest.py` | Sí — guías/recomendaciones como contexto del LLM |

Ningún módulo de una responsabilidad importa la lógica de otra. El cálculo no
sabe que existe BAM.xlsx; el RAG no sabe que existe el motor de cálculo.

## 2. BAM.xlsx: de requisito a adaptador

`food_db.py` ahora expone:

- `FoodNutrientRecord`: DTO normalizado (`id`, `name`, `normalizedName`,
  `portionQuantity`/`portionUnit` nullable, `energyKcal`, `proteinG`,
  `carbohydratesG`, `fatG`, `fiberG` nullable, `smaeGroup`/`smaeEquivalent`
  nullable, `sourceId`, `sourceVersion`, `sourceReference` nullable). Todos
  los nutrientes son `float`.
- `FoodDatabaseService` (ABC): `is_available()`, `search(query, limit)`,
  `status()`.
- `BamExcelFoodDatabase(FoodDatabaseService)`: adapta BAM.xlsx (hoja
  `BAM 18.1.1`, columnas `nombre_del_alimento`/`energ_kcal`/`protein`/
  `lipid_tot`/`carbohydrt`) al contrato. Si el archivo no existe o es
  inválido, `is_available()` es `False` y `search()` devuelve `[]`; nunca
  detiene el arranque (comportamiento heredado de la fase de "recursos
  externos", sin cambios).
- `get_food_database_service()`: punto único de acceso. **El resto del
  dominio debe llamar esta función, nunca importar BAM.xlsx directamente.**

`get_exact_macros()` (usada por la ruta heredada `POST /api/v1/generate-draft`,
anterior a Fase 1) se conserva intacta en su firma y ahora delega en
`search()`, para no romper ese flujo mientras siga vivo.

### Cómo sustituir BAM.xlsx por una fuente oficial

1. Implementar una clase que herede de `FoodDatabaseService` (por ejemplo
   `SmaeCsvFoodDatabase` o la fuente que se decida).
2. Reasignar `food_db._food_database_service` a esa instancia (o introducir
   una variable de entorno que elija la implementación en
   `get_food_database_service()`).
3. Nada fuera de `food_db.py` cambia: `get_exact_macros()` y cualquier código
   futuro que use `get_food_database_service()` siguen funcionando igual.

## 3. Manifiesto de conocimiento (RAG)

`services/knowledge_manifest.py` es la única puerta de entrada: el RAG nunca
procesa un archivo que no esté declarado aquí, y una fuente declarada cuyo
archivo no exista en disco simplemente se ignora (sin excepción).

Ruta configurable vía `ALIMENTIA_KNOWLEDGE_MANIFEST_PATH`
(default `/app/data/knowledge_base/manifest.json`).

Formato:

```json
{
  "version": "1.0",
  "sources": [
    {
      "id": "insp-tablas-2015",
      "name": "Tablas de composición de alimentos",
      "institution": "Instituto Nacional de Salud Pública (INSP)",
      "version": "2015",
      "file": "insp-tablas-2015.pdf",
      "type": "REFERENCE_TABLE"
    }
  ]
}
```

- `version`: versión de la base de conocimiento completa (`knowledgeBaseVersion`),
  no de una fuente individual. Se centraliza aquí — ningún otro módulo la
  hardcodea; se lee siempre vía `knowledge_manifest.knowledge_base_version()`.
- `sources[].id`: identificador estable (slug legible), no un UUID de base de
  datos. Se usa como `sourceId` en los metadatos de cada chunk indexado.
- `sources[].file`: nombre del archivo dentro de `ALIMENTIA_KNOWLEDGE_PATH`
  (`/app/data/pdfs` por defecto). Es también la clave natural con la que
  `repositories/knowledge.py::sync_knowledge_sources` busca/actualiza el
  `KnowledgeSource` correspondiente (columna `originalFilename`).
- `sources[].type`: uno de `GUIDELINE`, `REFERENCE_TABLE`, `REGULATION`,
  `OTHER`. Un valor desconocido cae a `OTHER` (no se rechaza el manifiesto
  completo por una entrada con un tipo nuevo).

El manifiesto real en `alimentia/data/knowledge_base/manifest.json` se deja
con `"sources": []` deliberadamente: no se inventó ninguna fuente para
cumplir el requisito de no cargar contenido ficticio en producción. El
ejemplo de arriba es solo documentación.

### Cómo agregar una fuente real

1. Copiar el PDF/documento a `alimentia/data/pdfs/`.
2. Agregar una entrada en `manifest.json` con `id`, `name`, `file` (y
   opcionalmente `institution`/`version`/`type`).
3. Reiniciar el backend (o llamar `POST /api/v1/ingest-pdfs`): al arrancar,
   `sync_knowledge_sources` da de alta el `KnowledgeSource` en base de datos
   y el hilo de ingesta indexa el archivo en Qdrant con esos metadatos.
4. Verificar en `GET /api/v1/sources` y `GET /api/v1/resources/status`.

## 4. KnowledgeSource: procedencia

Se agregaron (migración aditiva `202609060002_knowledge_source_provenance`,
sin tocar datos existentes):

- `checksum` (nullable): SHA-256 del archivo al momento de sincronizar, para
  detectar si cambió desde la última indexación.
- `originalFilename` (nullable): nombre de archivo declarado en el
  manifiesto; es la clave natural de sincronización.

`repositories/knowledge.py::sync_knowledge_sources(db, knowledge_dir)` se
ejecuta una vez al arrancar (en el `lifespan` de `main.py`, después de
`db.connect()`, antes de lanzar el hilo de ingesta). Es idempotente: una
fuente ya sincronizada se actualiza, no se duplica. Nunca da de alta una
fuente fuera del manifiesto.

## 5. RAG: solo fuentes autorizadas

`rag_engine.py::build_knowledge_base`:

1. Calcula `knowledge_manifest.authorized_documents(knowledge_dir)` —
   intersección entre lo declarado en el manifiesto y lo presente en disco.
2. Si no hay nada autorizado: WARNING, `{"status": "no_documents", ...}`, sin
   excepción (mismo contrato que la fase anterior).
3. Si hay documentos autorizados, los lee con
   `SimpleDirectoryReader(input_files=[...])` — **nunca** con el directorio
   completo, así un archivo presente pero no declarado jamás se lee.
4. Antes de indexar, cada `Document` recibe en su `metadata`:
   `sourceId`, `documentName`, `institution`, `sourceVersion` — provenientes
   del manifiesto, no inventados.
5. Indexa en la colección Qdrant `alimentia_knowledge_v1` (renombrada desde
   `medical_guidelines`, heredada del prototipo; sin documentos cargados
   todavía, la migración de nombre no tuvo puntos que preservar).

`RetrievedKnowledgeChunk` (Pydantic) y `KnowledgeBaseService.search(query,
top_k)`: interfaz de búsqueda documental para la futura generación (Fase 4).
Regla crítica implementada: si un nodo recuperado no trae `sourceId` y
`documentName` en sus metadatos, **se descarta** — nunca se expone un
fragmento sin procedencia verificable. Sin Qdrant/documentos disponibles,
`search()` devuelve `[]` en vez de lanzar una excepción.

`main.py::get_clinical_retriever` (ruta heredada `generate-draft`) ahora usa
la misma constante `KNOWLEDGE_COLLECTION`, en vez de un nombre repetido a mano.

## 6. Endpoints

- `GET /api/v1/sources`: lista `KnowledgeSource` reales (nombre, institución,
  versión, tipo, estado `isActive`, fecha de publicación, `originalFilename`,
  `checksum`). Sin fuentes registradas devuelve `[]`.
- `GET /api/v1/sources/{id}`: detalle; `404` si no existe.
- `GET /api/v1/resources/status`: `knowledgeBase` ahora incluye también
  `knowledgeBaseVersion` (del manifiesto), `authorizedSourceCount` (fuentes
  declaradas, existan o no en disco) e `indexedDocumentCount` (autorizadas Y
  presentes — mismo valor que `documentCount`, que se conserva por
  compatibilidad con la fase anterior).

Ninguna ruta nueva permite editar o borrar fuentes: solo lectura, como pide
esta fase.

## 7. Frontend

`sources/page.tsx` ya no usa `SOURCES_DATA` (mock). Consume `GET /api/v1/sources`
vía `getSources()`; mientras carga muestra "Cargando fuentes…", ante error un
`Notice` con reintento, y sin fuentes registradas: *"No hay fuentes de
conocimiento configuradas."* — sin registros de demostración inventados.

## 8. Pruebas

- `tests/test_knowledge_manifest.py` (11): manifiesto inexistente/JSON roto/
  forma inválida, manifiesto válido vacío, fuente válida registrada, entrada
  sin campos requeridos omitida, tipo desconocido → `OTHER`, documento no
  autorizado ignorado, fuente declarada sin archivo en disco ignorada,
  documento autorizado procesado con metadata conservada, versión y conteo
  de fuentes autorizadas.
- `tests/test_food_database.py` (5): adaptador BAM ausente/válido, mapeo
  completo a `FoodNutrientRecord` (nutrientes numéricos), `get_exact_macros`
  delega correctamente, `get_food_database_service()` funcional.
- `tests/test_sources_endpoint.py` (5): listado vacío, fuente inexistente
  (404), sincronización desde manifiesto visible en el listado y en el
  detalle, sincronización idempotente (no duplica), archivo no declarado en
  el manifiesto nunca se sincroniza.
- `tests/test_resources.py`: actualizado para el nuevo contrato — los tres
  casos que antes consideraban "listo" cualquier archivo presente ahora
  exigen que además esté autorizado por el manifiesto; se agregó el caso
  explícito de "documento no autorizado ignorado" a nivel de `resources/status`
  y de `build_knowledge_base`.

Las 87 pruebas de fases anteriores se mantienen sin modificar su cobertura
funcional (solo se ajustaron los fixtures de las pruebas de RAG que ahora
requieren un manifiesto, reflejando el cambio de contrato pedido en esta
fase). Total: 87 + 23 nuevas = **110 pruebas**, verificadas en Docker real.

## 9. Deuda explícita para Fase 4

- El `sourceId` que queda grabado en los metadatos de cada chunk indexado es
  el *slug* del manifiesto (`sources[].id`), no el UUID de `KnowledgeSource`
  en base de datos. Antes de escribir en `RetrievedSource` (que si exige el
  UUID real vía `knowledgeSourceId`), la generación de Fase 4 debe resolver
  slug → UUID (por ejemplo consultando `KnowledgeSource` por
  `originalFilename`, o agregando un índice slug→id si el volumen lo
  justifica). No se implementó aquí porque no hay generación todavía.
- `sync_knowledge_sources` no desactiva automáticamente una fuente que se
  quite del manifiesto; requeriría una decisión explícita (¿archivar?
  ¿eliminar? ¿marcar `isActive=false`?) que no correspondía definir en esta
  fase de infraestructura.
- `KnowledgeBaseService.search()` no se conecta a ningún endpoint todavía:
  es la interfaz que Fase 4 usará para poblar `RetrievedSource` durante la
  generación real.
