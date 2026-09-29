import { ExternalLink } from "lucide-react";
import { references } from "./content";
import { ValidationExample } from "./interactives";
import { Cite, DataTable, Note, Section } from "./primitives";
import styles from "./project.module.css";

export function Evaluation() {
  return <Section id="evaluacion" number="06" title="Evaluación y diseño experimental" lead="La utilidad se contrasta frente al proceso manual e incluye el trabajo que realiza el profesional después de generar el borrador.">
    <p>El protocolo del repositorio propone un estudio piloto comparativo con casos sintéticos o anonimizados de adultos sin patologías complejas. Cada profesional resolvería casos en condición manual y asistida, contrabalanceando el orden cuando sea posible para reducir el efecto de aprendizaje. El número de casos y de participantes del piloto está por definir; no se utiliza automáticamente el tamaño de la encuesta inicial.</p>
    <div className={styles.comparison}>
      <div><span>Condición de referencia</span><h3>Proceso manual</h3><p>Herramientas habituales, tablas y criterio del profesional. Registrar captura, elaboración, revisión y corrección mediante una planilla de estudio.</p></div>
      <div><span>Condición experimental</span><h3>Proceso asistido</h3><p>Captura en AlimentIA, cálculo, generación con BAM y RAG, revisión, edición y aprobación. Combinar la instrumentación del sistema con el registro del tiempo total.</p></div>
    </div>
    <h3>Variables y criterios de medición</h3>
    <DataTable caption="Tabla 6. Qué medir y cómo interpretar el resultado" headers={["Variable", "Medición", "Criterio o precaución"]} rows={[
      ["Tiempo total", "100 × (T manual − T asistido) / T manual.", "Incluir captura y revisión. La duración del LLM por sí sola no demuestra ahorro."],
      ["Desviación nutricional", "100 × |valor del plan − referencia| / referencia, con referencia > 0.", "Informar energía y cada macro por separado; meta académica ≤5 %."],
      ["Error absoluto medio (MAE)", "Media de |valor calculado − valor de referencia| por variable.", "Expresar kcal o g según corresponda; no mezclar unidades en un solo promedio."],
      ["Intervención profesional", "Planes con cambios menores / planes evaluados; guardados y regeneraciones.", "Meta >80 % de cambios menores. Un número de guardados no mide por sí solo la magnitud del cambio."],
      ["Respaldo documental", "Recomendaciones realmente sustentadas / recomendaciones revisadas.", "Un fragmento recuperado no equivale a una recomendación respaldada."],
      ["Restricciones y alertas", "Omisiones, detecciones y falsas alertas en casos definidos.", "Reportar incidentes; ausencia de alertas no acredita seguridad integral."],
      ["Usabilidad y calidad", "Tareas completadas, errores y valoración profesional.", "Pertinencia, claridad, coherencia y factibilidad requieren evaluación humana."],
    ]} />
    <p className={styles.caption}>Diseño de evaluación, no resultados. Fuentes: propuesta del equipo, Entrega 2 y <code>EVALUATION_PROTOCOL.md</code> del repositorio.</p>
    <h3>Procedimiento propuesto</h3>
    <ol className={styles.steps}>
      <li><strong>Preparar casos y referencias.</strong> Definir entradas, restricciones y criterios de revisión con profesionales; separar los casos usados para ajustar el sistema de los reservados para evaluación.</li>
      <li><strong>Fijar la configuración.</strong> Registrar modelo, prompt, reglas, versión del corpus, hardware y condiciones de ejecución.</li>
      <li><strong>Ejecutar ambas condiciones.</strong> Contrabalancear el orden y registrar duración total, incidencias y resultado. Repetir generaciones cuando se estudie variabilidad, sin seleccionar solo las favorables.</li>
      <li><strong>Evaluar el plan final.</strong> Aplicar criterios homogéneos de calidad, precisión, restricciones y edición; conservar el historial que explica cómo se obtuvo.</li>
      <li><strong>Analizar y aprender.</strong> Presentar diferencias por caso, medianas y dispersión; declarar denominadores, faltantes y fallos. El alcance exploratorio limita cualquier afirmación de superioridad general.</li>
    </ol>
    <details className={styles.details}>
      <summary>Evidencia automática y evidencia que debe recogerse</summary>
      <p>Las rutas de métricas y trazabilidad registran duración de generación, tiempo desde la primera generación hasta aprobación, desviaciones iniciales y finales, validaciones, versiones, ediciones, regeneraciones y fuentes recuperadas.</p>
      <p>El tiempo manual, el inicio de la captura, la satisfacción, el carácter menor o mayor de una edición y la calidad clínica requieren instrumentos adicionales. La instrumentación existente no debe confundirse con un estudio ya ejecutado.</p>
      <p>El protocolo separa los errores técnicos y los casos no aprobados. Para evitar sesgo de supervivencia, el informe del piloto debe mostrar además el total de intentos, cuántos fallaron y por qué, incluso cuando no entren en una comparación de tiempos de planes terminados.</p>
    </details>
    <ValidationExample />
    <Note title="Ejemplo de por qué medir todo el proceso">
      <p>En un escenario hipotético, un plan manual tarda 40 minutos y el asistido 25, incluida la revisión: el ahorro sería 37.5 %. Si la corrección eleva el total asistido a 45 minutos, el cambio sería −12.5 %. La rapidez de generación no basta para aceptar la hipótesis. Estas cifras son ilustrativas y no proceden de pruebas del proyecto.</p>
    </Note>
    <h3>Alineación con la asignatura</h3>
    <p>Esta memoria presenta el problema y la justificación, objetivos observables, antecedentes, desarrollo conceptual, metodología, implementación, validación propuesta, conclusiones y bibliografía. La rúbrica valora la estructura y el estilo (20 %), el alcance, implementación, verificación y coherencia con los objetivos (50 %), y la exposición (30 %). La página apoya la explicación del proyecto; el documento final y el video de exposición constituyen entregables académicos distintos. <Cite id="ref-rubrica">UNIR, s. f.-c</Cite> <Cite id="ref-guia">UNIR, s. f.-a</Cite></p>
  </Section>;
}

export function Conclusions() {
  return <Section id="conclusiones" number="07" title="Conclusiones y trabajo futuro" lead="La aportación verificable es una arquitectura de asistencia trazable; su impacto profesional debe demostrarse con evidencia experimental.">
    <p>El estudio de necesidades permitió orientar la propuesta hacia un primer borrador editable, con fuentes y cálculo independiente. La selección conceptual favoreció integrar al nutriólogo en el flujo de decisión. El repositorio materializa módulos de captura, cálculo, recuperación, generación, validación y revisión que permiten preparar una evaluación del sistema completo.</p>
    <p>El trabajo ofrece una aplicación concreta del procesamiento del lenguaje natural y la recuperación de información, articulada con ingeniería de datos y desarrollo iterativo. Su principal contribución consiste en separar la generación probabilística de las comprobaciones numéricas y conservar información sobre cómo se produjo y modificó cada plan.</p>
    <DataTable caption="Tabla 7. Balance de los objetivos" headers={["Aportación", "Estado de la evidencia"]} rows={[
      ["Identificación de necesidades y diseño", "Documentados en las entregas: encuesta, alternativas, matriz y backlog."],
      ["Flujo técnico integrado", "Implementado en el repositorio; requiere verificación funcional en cada configuración de despliegue."],
      ["Ahorro de tiempo y utilidad profesional", "Hipótesis pendientes de contrastar en el piloto comparativo."],
      ["Precisión nutricional y seguridad", "Existen validaciones técnicas; no se ha demostrado validación clínica integral."],
      ["Adherencia automatizada al SMAE", "Pendiente: el material documental no equivale a reglas estructuradas de equivalencias."],
    ]} />
    <h3>Líneas de continuidad</h3>
    <ul className={styles.steps}>
      <li><strong>Evaluación profesional:</strong> ejecutar el piloto, documentar fallos y analizar el tiempo total y la magnitud de las correcciones.</li>
      <li><strong>Calidad de recuperación:</strong> comparar configuraciones de fragmentación y recuperación con consultas y evidencia de referencia.</li>
      <li><strong>Datos alimentarios:</strong> ampliar coincidencias verificables, conversiones de unidades y equivalencias estructuradas autorizadas.</li>
      <li><strong>Modelos y rendimiento:</strong> comparar modelos y hardware bajo las mismas condiciones, midiendo calidad y latencia.</li>
      <li><strong>Operación y gobernanza:</strong> incorporar identidad autenticada, controles de acceso, gestión del consentimiento y protección del almacenamiento.</li>
    </ul>
    <Note title="Conclusión de investigación" tone="green"><p>La viabilidad de integrar estas tecnologías es una aportación técnica. Determinar si esa integración mejora la práctica requiere medirla: el éxito del proyecto se vincula al trabajo útil que aporta al profesional y a la calidad de la revisión, no solo a su capacidad de generar texto.</p></Note>
  </Section>;
}

export function References() {
  return <Section id="referencias" number="08" title="Referencias y base documental" lead="Fuentes académicas, entregas del equipo y documentación técnica que sustentan esta sección.">
    <p>Las citas enlazan con las entradas correspondientes. Los materiales internos se identifican por título y localización; los artículos y guías públicas incluyen enlaces a su fuente. La síntesis toma la Entrega 2 como referencia metodológica más desarrollada y contrasta las afirmaciones de implementación con el código.</p>
    <ol className={styles.references}>{references.map(ref => <li id={ref.id} key={ref.id}>
      <p>{ref.author} ({ref.year}). <em>{ref.title}</em> {ref.publication}</p>
      {ref.href ? <a href={ref.href} target="_blank" rel="noreferrer">Consultar fuente <ExternalLink size={13} aria-hidden="true" /></a> : <span>Documento aportado por el equipo</span>}
    </li>)}</ol>
    <details className={styles.details}>
      <summary>Documentos complementarios y trazabilidad técnica</summary>
      <p>También se revisaron la <em>Propuesta de Innovación - 3033E</em>, el borrador <em>Trabajo de Innovación - Equipo 3033E</em> y <em>Antecedentes_LLM_Nutricion_Planes_Dieteticos</em>. Este último se identifica como material de apoyo elaborado con IA; sus afirmaciones no se adoptan como evidencia primaria sin contraste.</p>
      <p>La implementación descrita se fundamenta en los servicios de cálculo, base alimentaria, motor RAG, generación y validación; en el manifiesto de conocimiento y Docker Compose; y en los documentos <code>NORMALIZATION_3NF.md</code> y <code>EVALUATION_PROTOCOL.md</code>. La nota de mantenimiento <code>ABOUT_PROJECT_SOURCES.md</code> registra la relación entre contenidos y fuentes.</p>
      <p><a className={styles.textLink} href="https://github.com/Yudikioros/UNIR-3033E" target="_blank" rel="noreferrer">Consultar el repositorio del proyecto <ExternalLink size={14} aria-hidden="true" /></a></p>
    </details>
    <div className={styles.closing}><p>AlimentIA · Equipo 3033E</p><span>Maestría en Inteligencia Artificial · Universidad Internacional de La Rioja</span></div>
  </Section>;
}
