# Integración y validación de recursos reales (previa a Fase 6)

Esta etapa **no es una fase funcional nueva**. No reabre Fase 3.5, no modifica
el motor de cálculo de Fase 3 ni el flujo human-in-the-loop de Fase 5. Su
único objetivo es conectar los recursos reales (BAM.xlsx y los PDFs
autorizados) que antes eran arquitectura vacía, sin inventar datos y sin
mezclar fuentes estructuradas con conocimiento documental.

## 1. BAM identificado

`alimentia/data/tables/BAM.xlsx` — Base de Alimentos de México, versión
18.1.1 (nota interna del archivo: "Base de Alimentos de México (BAM), versión
18.1.1, 2021"). 499,565 bytes.

## 2. Versión

18.1.1 / 2021. Estos valores ya estaban codificados como `SHEET_NAME`/
`FOOD_SOURCE_VERSION` en `food_db.py` desde Fase 3.5 y coinciden exactamente
con el archivo real; se agregó `FOOD_SOURCE_PUBLICATION_YEAR = 2021` y
`FOOD_SOURCE_NAME` para exponerlos en `/resources/status`.

## 3. Estructura verificada

- Hoja: `BAM 18.1.1` (coincide con `SHEET_NAME` ya configurado).
- Encabezados en la fila 13 (`HEADER_ROW = 12`, base cero) — sin cambios.
- 30 columnas; las usadas por el dominio: `codigomex2`, `nombre_del_alimento`,
  `energ_kcal`, `protein`, `lipid_tot`, `carbohydrt` (`fiber_td` disponible
  pero no obligatoria).
- 2045 filas de datos, 2037 nombres únicos, 8 ocurrencias de nombres
  duplicados con `codigomex2` distinto (p.ej. dos filas "ACEITE, DE CANOLA").
- Valores ND reales: 1 fila sin `energ_kcal`, 3 filas sin `protein`.
- 82 de 2045 nombres contienen acentos; el resto no.

## 4. Número de registros válidos

2045 filas leídas; de ellas, cualquier búsqueda que recaiga en una fila con
un nutriente requerido en ND queda excluida del resultado (nunca se inventa
el dato faltante). Los 2037 nombres únicos y los duplicados por código son
todos consultables mediante `food_db.search()`.

## 5. Edición SMAE activa

**5a Edición** (`SMAE 5ta Edición.pdf`) queda `active: true`; la **4a
Edición** queda `active: false` (referencia histórica conservada en el
manifiesto, no se ingiere). Justificación:

- Ninguna de las dos ediciones es extraíble de forma confiable como datos
  ESTRUCTURADOS: la 4a es narrativa/metodológica con artefactos de
  codificación de fuente; la 5a es una tabla plana cuya extracción lineal de
  texto de PDF **rompe la correspondencia fila↔alimento** a partir de la
  página 4 (quedan filas de números sin nombre de alimento asociado).
- Por esa razón **no se implementó `FoodEquivalentService`/
  `FoodEquivalentRecord`** en esta etapa: hacerlo con la herramienta
  disponible (extracción de texto plano) arriesgaba inventar asociaciones
  alimento↔cantidad falsas, violando el principio de "nunca inventar datos".
  Ambas ediciones se tratan como fuente documental para RAG únicamente
  (categoría B de la sección 7), nunca como fuente de equivalentes SMAE
  verificados. `DietPlanFood.smaeEquivalent` sigue siendo `null` en todo
  alimento generado (sin cambios respecto a Fase 4/5).

## 6. Fuentes RAG incluidas

| id | documento | institución | año | tipo | scope |
|---|---|---|---|---|---|
| `ss-guia-alimentos-2011` | Guía de Alimentos para la Población Mexicana | Secretaría de Salud | 2011 | GUIDELINE | adult_general |
| `anm-guias-sobrepeso-obesidad-2014` | Guías alimentarias y de actividad física en contexto de sobrepeso y obesidad en la población mexicana | Academia Nacional de Medicina de México | 2014 | GUIDELINE | adult_general |
| `nom-043-ssa2-2012` | NOM-043-SSA2-2012 | Secretaría de Salud | 2012 | REGULATION | adult_general |
| `smae-5a-edicion` | SMAE 5a Edición | — | — | REFERENCE_TABLE | adult_general |
| `smae-4a-edicion` (inactiva) | SMAE 4a Edición | — | — | REFERENCE_TABLE | adult_general |

Institución/año se confirmaron leyendo el propio documento (nunca inventados):

- **Guía de alimentos SS.pdf**: página del "Directorio" nombra a Dr. José
  Ángel Córdova Villalobos como Secretario de Salud (su gestión real fue
  2006–2012); metadata de creación del PDF: 2011.
- **Guías Alimentarias.pdf**: portada declara el título completo y la "Mesa
  Directiva de la Academia Nacional de Medicina 2013-2014".
- **NOM-043-SSA2-2012.pdf**: el año y la designación "SSA2" (Secretaría de
  Salud) forman parte del identificador oficial de la norma, tomado
  directamente de la metadata de título del PDF.
- **SMAE 4a/5a Edición**: no se encontró una institución editorial explícita
  en el texto inspeccionado (se buscó "Secretaría de Salud", "A.C.",
  "Fomento..." sin resultado) ni una fecha de publicación editorial (solo
  fecha de creación del archivo PDF, que no se declara como año de
  publicación para no inventar un dato). Quedan con `institution: null`,
  `publicationYear: null`.

## 7. Fuentes excluidas y por qué

- **`GUÍAS ALIMENTARIAS 2.pdf`** — `NOT_USABLE`. 0 caracteres extraíbles en
  sus 96 páginas; `pypdf` reporta cientos de errores
  "Ignoring wrong pointing object" / "incorrect header check" al parsearlo:
  streams internos corruptos, no una simple portada escaneada.
- **`TC ácidos grasos.pdf`** — `NOT_USABLE`. Mismo patrón: 0 caracteres
  extraíbles, con los mismos errores de descompresión.

Ninguno de los dos se agregó al manifiesto solo porque el archivo existe en
disco.

## 8. Manifiesto final

`alimentia/data/knowledge_base/manifest.json`, versión `"2.0"`, 5 fuentes
activas + 1 histórica (ver tabla arriba). El esquema se extendió de forma
retrocompatible con `publicationYear`, `active` (default `true` si se omite)
y `scope` (lista; vacía si se omite = sin restricción, para no romper
manifiestos de Fase 3.5/4/5 existentes). BAM nunca aparece aquí: no es un
documento RAG.

## 9. Estado de Qdrant

Colección `alimentia_knowledge_v1`. Antes de esta etapa estaba vacía (0
puntos, manifiesto `sources: []`). Al registrar el manifiesto real y
reiniciar el backend (que sincroniza `KnowledgeSource` e ingiere de forma
automática al arrancar), la primera ingesta reveló un defecto real y previo
a esta etapa: **`SimpleDirectoryReader` de LlamaIndex, sin el paquete
opcional `llama-index-readers-file` instalado, no tiene lector dedicado para
`.pdf` y decodifica el binario del archivo como si fuera texto plano** —
produce basura ilegible (bytes de imágenes JPEG embebidas, sintaxis interna
del PDF como `/Pages /Parent 1135 0 R`) en vez del contenido real, aunque la
metadata de procedencia (`sourceId`, institución, scope) quedaba correcta.
Esto nunca se había detectado porque el manifiesto estuvo vacío durante
Fase 3.5/4/5.

**Corrección aplicada**: `rag_engine.py` ahora registra un `_PyPdfReader`
explícito (usa `pypdf`, ya dependencia del proyecto) como
`file_extractor={".pdf": _PyPdfReader()}` para `SimpleDirectoryReader`. Se
limpió la colección (`DELETE` en Qdrant; nunca se tocó `data/db`) y se
reingirió. El resultado final: 424 puntos indexados, contenido verificado
como texto real y legible (ver control de búsquedas abajo).

## 10. Pruebas de búsqueda de control

Ejecutadas contra el RAG ya poblado con las fuentes autorizadas, tras la
corrección del extractor de PDF:

| Query | sourceId recuperado | score | Fragmento (recortado) |
|---|---|---|---|
| características de una dieta correcta | `ss-guia-alimentos-2011` | 0.617 | "Peso normal... un plan de alimentación servirá para mejorar y mantener hábitos..." |
| características de una dieta correcta | `anm-guias-sobrepeso-obesidad-2014` | 0.594 | "Específicamente se recomiendan a) dietas basadas en productos vegetales..." |
| consumo de agua simple | `anm-guias-sobrepeso-obesidad-2014` | 0.507 | "El agua simple se considera la elección más saludable para lograr una correcta hidratación..." |
| consumo de agua simple | `anm-guias-sobrepeso-obesidad-2014` | 0.461 | "Hay que tomar agua simple. El agua es la principal fuente de hidratación..." |
| grupos de alimentos | `ss-guia-alimentos-2011` | 0.593 | "SIMBOLOGÍA... Usted encontrará clasificados los grupos de alimentos por colores..." |
| grupos de alimentos | `ss-guia-alimentos-2011` | 0.591 | "Grupo: Alimentos de origen animal... Ración Promedio Energía 55 kcal..." |
| recomendaciones para verduras y frutas | `ss-guia-alimentos-2011` | 0.577 | "...VERDURAS II: Grupo: Verduras Ración Promedio Energía 25 kcal..." |
| recomendaciones para verduras y frutas | `anm-guias-sobrepeso-obesidad-2014` | 0.573 | "...las frutas y verduras de color naranja (papaya, mango, zanahoria)..." |
| porciones de adultos | `nom-043-ssa2-2012` | 0.492 | "...para adultos... enfoques para la consejería, entrevista motivacional..." (índice) |
| cereales integrales | `nom-043-ssa2-2012` | 0.480 | "4.3.2.6.2 Se debe destacar la importancia de combinar cereales con leguminosas..." |
| cereales integrales | `anm-guias-sobrepeso-obesidad-2014` | 0.405 | "Los cereales enteros e integrales son una buena fuente de vitaminas..." |

En todas las consultas, el `sourceId` recuperado corresponde siempre a un id
declarado y activo en el manifiesto — nunca apareció un documento no
autorizado, ni las dos fuentes `NOT_USABLE` excluidas. Se verificó la cadena
completa de trazabilidad: `sourceId` (slug del manifiesto) →
`resolve_source_id()` → UUID real de `KnowledgeSource` → fila persistida en
`RetrievedSource` con `documentName`/`institution` reales (confirmado en la
generación real, sección 11). Una fracción de fragmentos (p.ej. "Cuadro 4.4"
en "cereales integrales") conserva artefactos de codificación de fuente CID
específicos de esa página del PDF original — no son garantía de texto
perfecto en el 100% de las páginas, pero la inmensa mayoría del contenido es
español legible y correcto.

## 11. Resultado de una generación real

Se generó la versión 3 (`POST /consultations/6b32a5d9.../generate-draft`,
consulta demo de María González, ya calculada con Mifflin-St Jeor) sin tocar
v1 ni v2, que permanecen intactas y en estado `DRAFT`. Generación real
contra Ollama (`llama3.2:3b`), 447.9 segundos.

- `knowledgeBaseUsed=true`: 3 fuentes recuperadas, todas resueltas a
  `KnowledgeSource` reales — `ss-guia-alimentos-2011` (Guía de Alimentos
  para la Población Mexicana, Secretaría de Salud) y
  `anm-guias-sobrepeso-obesidad-2014` (×2, Academia Nacional de Medicina de
  México) — con `retrievalScore` real (0.66, 0.62, 0.61).
- `foodDatabaseUsed=true`, pero **0 de 11 alimentos generados coincidieron
  de forma confiable con BAM** (validación `FOOD_NUTRIENTS_PARTIALLY_VERIFIED`,
  INFO/no bloqueante): el LLM usó unidades como "taza"/"pieza" en vez de
  gramos, y nombres genéricos ("Avena", "Pescado") que no calzan exactamente
  con la nomenclatura BAM — exactamente el comportamiento conservador
  esperado de la sección 24 (mejor "sin verificar" que inventar una
  conversión). `smaeEquivalent` es `null` en los 11 alimentos.
- El borrador quedó con una validación bloqueante real
  (`INCOMPLETE_NUTRITION_DATA`, ERROR): no todos los alimentos incluyen
  calorías. No se exigió que el resultado fuera aprobable, y no lo es —
  consistente con el flujo human-in-the-loop de Fase 5 (el nutriólogo
  revisa, no se fuerza una aprobación).

## 12. Limitaciones conocidas / deuda técnica explícita

- SMAE 4a/5a edición se usan solo como texto RAG, no como fuente estructurada
  de equivalentes: `smaeEquivalent` seguirá siendo `null` hasta que exista
  una herramienta de extracción de tablas con reconocimiento de layout (o una
  fuente tabular limpia) que permita implementar `FoodEquivalentService` sin
  arriesgar inventar asociaciones.
- El filtrado por `scope` es a nivel de documento completo, no por fragmento:
  un documento general etiquetado `adult_general` puede contener secciones
  puntuales sobre población pediátrica y un fragmento de esas secciones
  podría recuperarse igual. Mitigarlo requeriría metadata por sección, fuera
  de alcance de esta etapa.
- La precedencia BAM > LLM en la generación (sección 24) solo aplica a
  coincidencias EXACTAS de nombre (sin acentos/mayúsculas) y unidades en
  gramos; es intencionalmente conservadora (mejor un alimento "sin verificar"
  que una conversión de unidad inventada), por lo que en la práctica pocos
  alimentos generados por el LLM calzan exactamente con la nomenclatura de
  BAM.
- `config/page.tsx` (Configuración) sigue mostrando valores estáticos de
  ejemplo (versión "KB-1.0", "5" documentos, fecha fija): no tiene ningún
  fetch al backend todavía, a diferencia de `sources/page.tsx` que sí está
  conectado. No se tocó en esta etapa por no ser una ampliación de soporte
  existente, sino una funcionalidad nueva — decisión deliberada para no
  exceder el alcance de "no rediseñar".
- La institución/fecha de las ediciones SMAE no pudieron confirmarse desde el
  propio documento; quedan `null` en vez de inventarse.
- El extractor de PDF (`_PyPdfReader`, basado en `pypdf`) usa
  `page.extract_text()` por página; en páginas con fuentes CID/embebidas
  específicas puede producir fragmentos parcialmente ilegibles (no bloquea
  la ingesta, ni la búsqueda, ni la trazabilidad — solo reduce la calidad de
  ese fragmento puntual). Instalar `llama-index-readers-file` en el futuro
  daría acceso a extractores más robustos si esto se vuelve un problema
  recurrente.

**Fase 6 no ha comenzado.** Esta etapa no modificó el motor de cálculo de
Fase 3 ni el flujo de edición/aprobación/rechazo de Fase 5.
