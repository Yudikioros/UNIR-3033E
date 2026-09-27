import Link from "next/link";
import { decisions } from "./content";
import { ArchitectureExplorer } from "./interactives";
import { Cite, DataTable, Note, Section } from "./primitives";
import styles from "./project.module.css";

export function DataAndArchitecture() {
  return <Section id="arquitectura" number="04" title="Datos y arquitectura" lead="Cálculos reproducibles, evidencia recuperable y generación supervisada.">
    <p>La arquitectura separa responsabilidades para que una respuesta del modelo pueda examinarse y corregirse. El análisis de datos comprende tres ámbitos: las necesidades recogidas en la encuesta, la calidad de los datos de entrada y del corpus, y las métricas del proceso de generación y revisión.</p>
    <ArchitectureExplorer />
    <h3>Del dato a la evidencia</h3>
    <dl className={styles.dataStages}>
      <div><dt><span>01</span>Preparar</dt><dd>Comprobar campos obligatorios, rangos técnicos y unidades. Separar preferencias, alergias y exclusiones. Para BAM, validar la hoja y las columnas; descartar filas sin nombre y normalizar acentos y mayúsculas al buscar, conservando el texto original.</dd></div>
      <div><dt><span>02</span>Recuperar</dt><dd>Extraer texto de los PDF autorizados, asociarlo a metadatos y generar representaciones vectoriales. LlamaIndex organiza la indexación en Qdrant y la consulta semántica, separada de la búsqueda tabular de nutrientes.</dd></div>
      <div><dt><span>03</span>Auditar</dt><dd>Conservar entradas, método de cálculo, versión del prompt y del modelo, fuentes recuperadas, validaciones y cambios del plan. Los valores ausentes no deben interpretarse como ceros nutricionales.</dd></div>
    </dl>
    <Note title="Ejemplo reproducible de escalado">
      <p className={styles.equation}>150 g × 120 kcal / 100 g = <strong>180 kcal</strong></p>
      <p>Si un registro sintético contiene 120 kcal por 100 g, una porción de 150 g aporta 180 kcal según esa tabla. La operación es determinística. Solo se puede atribuir al registro correcto cuando la identidad del alimento y la unidad están verificadas. Ejemplo didáctico, no una recomendación alimentaria.</p>
    </Note>
    <h3>RAG: recuperar antes de generar</h3>
    <p>RAG combina generación con recuperación de información externa al conocimiento paramétrico del modelo. La propuesta de Lewis et al. (2020) aporta el antecedente metodológico de esta combinación; AlimentIA la adapta a un corpus documental seleccionado y a un flujo profesional. Indexar documentos no equivale a entrenar o ajustar los pesos del LLM. <Cite id="ref-lewis">Lewis et al., 2020</Cite></p>
    <ol className={styles.steps}>
      <li><strong>Curación documental.</strong> El manifiesto identifica fuente, institución, edición, alcance y estado activo. La versión revisada incluye guías alimentarias, una norma de orientación alimentaria y material de referencia como SMAE; su autorización en el corpus no certifica automáticamente su vigencia o pertinencia para cada caso.</li>
      <li><strong>Extracción e indexación.</strong> pypdf extrae el texto; LlamaIndex prepara las unidades documentales y embeddings multilingües con <code>paraphrase-multilingual-MiniLM-L12-v2</code>. Qdrant almacena la representación vectorial y los metadatos.</li>
      <li><strong>Consulta contextual.</strong> La consulta se construye a partir del contexto de la generación. El recuperador solicita cinco candidatos y la configuración por defecto considera hasta tres; se descartan resultados sin procedencia y los que declaran un alcance incompatible.</li>
      <li><strong>Generación y registro.</strong> Los fragmentos seleccionados se incorporan al prompt junto con los requerimientos y datos tabulares. La generación conserva referencias al contenido recuperado para su inspección.</li>
    </ol>
    <p>Una puntuación de similitud indica proximidad semántica, no veracidad ni respaldo clínico. El tamaño de los fragmentos, el número de resultados, la cobertura del corpus y los documentos sin texto extraíble deben examinarse en la evaluación. Esta versión no demuestra por sí sola que cada afirmación generada esté respaldada por una cita.</p>
    <h3>Análisis y calidad de los datos</h3>
    <DataTable caption="Tabla 5. Fuentes, tratamiento y límites de interpretación" headers={["Datos", "Tratamiento", "Control o límite"]} rows={[
      ["Encuesta a profesionales", "Frecuencias por respuesta y perfil; síntesis de necesidades.", "n = 13; resultados descriptivos, sin generalización poblacional."],
      ["Datos de consulta", "Campos tipados, unidades explícitas y rangos técnicos.", "La validez de formato no prueba la validez clínica."],
      ["BAM 18.1.1", "Lectura de Excel, nombres normalizados y escalado por porción.", "Coincidencias exactas normalizadas y gramos; los demás valores quedan sin verificar."],
      ["Documentos del corpus", "Extracción textual, metadatos, embeddings y recuperación.", "Revisar legibilidad, duplicados, versiones, pertinencia y cobertura."],
      ["Planes y revisiones", "Totales, desviaciones, tiempos, versiones y cambios.", "Separar faltantes, fallos técnicos y casos no aprobados; no imputar éxitos."],
    ]} />
    <h3>Implementación, despliegue y mantenimiento</h3>
    <div className={styles.stackGrid}>
      <div><h4>Interfaz</h4><p>Next.js, React y TypeScript para captura, visualización del plan, edición y consulta de fuentes.</p></div>
      <div><h4>Servicios</h4><p>FastAPI y Python para contratos, cálculo, orquestación del LLM y reglas de validación.</p></div>
      <div><h4>Persistencia</h4><p>Prisma y SQLite para consultas, planes y auditoría. El diseño separa entidades en tercera forma normal.</p></div>
      <div><h4>Recuperación e inferencia</h4><p>LlamaIndex, embeddings de Hugging Face, Qdrant y Ollama, coordinados mediante Docker Compose.</p></div>
    </div>
    <p>La implementación se organiza en incrementos de captura, cálculo, recuperación, generación, aprobación y evaluación. El despliegue local separa interfaz, API, Qdrant y Ollama en contenedores. La puesta en marcha requiere preparar modelos y corpus, comprobar la conexión con la base de datos y verificar el flujo completo.</p>
    <p>El mantenimiento debe revisar las fuentes y sus versiones, reindexar cuando proceda, respaldar los datos y repetir las pruebas al cambiar el modelo, el prompt o las reglas. La documentación técnica registra un respaldo y verificación de preservación de datos durante las migraciones. La reproducibilidad de un experimento exige conservar también el entorno, el hardware y la configuración utilizados.</p>
    <p><Link className={styles.textLink} href="/sources">Explorar las fuentes en la aplicación →</Link></p>
  </Section>;
}

export function TechnicalDecisions() {
  return <Section id="decisiones" number="05" title="Obstáculos y decisiones técnicas" lead="Cada decisión resuelve una dificultad concreta y conserva límites que deben hacerse visibles.">
    <p>Los obstáculos siguientes se identifican al contrastar las entregas con la implementación revisada. Se documenta su respuesta técnica y el coste o limitación que permanece, evitando equiparar la presencia de un componente con la resolución completa del problema.</p>
    <div className={styles.decisions}>{decisions.map((item, index) => <article key={item.title}>
      <div className={styles.decisionHeading}><span>{String(index + 1).padStart(2, "0")}</span><h3>{item.title}</h3></div>
      <dl><div><dt>Obstáculo</dt><dd>{item.obstacle}</dd></div><div><dt>Decisión</dt><dd>{item.decision}</dd></div><div><dt>Límite</dt><dd>{item.tradeoff}</dd></div></dl>
    </article>)}</div>
    <Note title="Una diferencia relevante entre objetivo e implementación" tone="amber">
      <p>La Entrega 2 establece una meta de desviación de 5 % tanto en energía como en macronutrientes. El validador actual usa 5 % para energía y 10 % para macronutrientes. Aprobar con estas reglas no demuestra haber alcanzado la meta académica de 5 % en ambos casos. La evaluación debe registrar la diferencia y resolverla con un criterio profesional documentado.</p>
    </Note>
    <h3>Ética, privacidad y uso responsable</h3>
    <p>La evaluación propuesta emplea casos sintéticos o anonimizados, minimiza datos identificables y conserva el juicio profesional. El uso local del modelo permite controlar parte del recorrido de los datos, pero requiere una política de accesos, copias de seguridad y tratamiento de información antes de trabajar con datos reales. El sistema debe comunicar las fuentes ausentes, los datos no verificados y sus limitaciones de alcance.</p>
    <p>La muestra de necesidades y el corpus pueden introducir sesgos de especialidad, disponibilidad de alimentos y contexto regional. La evaluación debe analizar esos límites y documentar quién revisó los resultados. Las alertas automáticas son apoyo a la revisión; no sustituyen un análisis integral de riesgos del caso.</p>
  </Section>;
}
