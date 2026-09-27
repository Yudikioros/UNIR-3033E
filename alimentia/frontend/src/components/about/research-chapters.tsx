import { backlog, survey } from "./content";
import { Cite, DataTable, Note, Section } from "./primitives";
import styles from "./project.module.css";

export function Introduction() {
  return <Section id="introduccion" number="01" title="Introducción" lead="AlimentIA estudia cómo integrar inteligencia artificial generativa en un proceso de planificación dietética trazable y supervisado.">
    <p>La elaboración de un plan dietético exige transformar datos antropométricos, preferencias y restricciones en una propuesta coherente de alimentos y porciones. El trabajo incluye cálculos, consulta de fuentes, redacción y sucesivas correcciones. AlimentIA surge como proyecto de investigación e innovación de la Maestría en Inteligencia Artificial de la Universidad Internacional de La Rioja, dentro del Seminario de Innovación en Inteligencia Artificial.</p>
    <p>La propuesta combina un motor de cálculo determinístico, una base alimentaria estructurada, recuperación aumentada por generación (RAG) y un modelo de lenguaje grande (LLM). El resultado se presenta como borrador: el nutriólogo examina la evidencia, modifica el contenido y conserva la decisión final. La contribución se centra en esta integración y en la posibilidad de estudiar su utilidad dentro del flujo profesional. <Cite /></p>
    <div className={styles.keyStats} aria-label="Contexto de la encuesta exploratoria">
      <div><strong>13</strong><span>profesionales de la nutrición encuestados</span></div>
      <div><strong>61.5 %</strong><span>reporta al menos 30 minutos para concluir y enviar el menú</span></div>
      <div><strong>76.9 %</strong><span>se preocupa por datos inventados o cálculos incorrectos</span></div>
    </div>
    <p className={styles.caption}>Encuesta exploratoria del equipo; estos datos describen necesidades, no resultados de eficacia del prototipo. <Cite /></p>
    <h3>Alcance de la investigación</h3>
    <p>El MVP se dirige a profesionales que elaboran planes para adultos sin patologías clínicas complejas. Se estudian la captura, el cálculo, la generación de borradores, la recuperación de fuentes, las validaciones y el ciclo de revisión. La atención pediátrica, las decisiones diagnósticas y el manejo integral de interacciones fármaco-alimento quedan fuera de la validación de esta primera versión.</p>
    <Note title="Cómo leer esta memoria">
      <p>Las entregas sustentan el problema y la metodología; el repositorio permite describir la implementación. Las metas de precisión, ahorro de tiempo y utilidad profesional se identifican como objetivos pendientes de contrastar mediante el estudio piloto. La sección sigue la estructura de introducción, desarrollo de la innovación, evaluación, conclusiones y referencias solicitada por la asignatura. <Cite id="ref-instrucciones">UNIR, s. f.-b</Cite></p>
    </Note>
    <h3>Antecedentes y oportunidad de innovación</h3>
    <p>Azimi et al. (2025) evaluaron modelos de lenguaje con 1,050 preguntas del examen para dietistas registrados y observaron variación según el modelo, el dominio y la estrategia de prompting. Bragazzi et al. (2025) compararon conocimiento nutricional de agentes conversacionales y grupos humanos. Estos estudios aportan antecedentes sobre conocimiento y consistencia; no constituyen una validación del flujo completo de AlimentIA. <Cite id="ref-azimi">Azimi et al., 2025</Cite> <Cite id="ref-bragazzi">Bragazzi et al., 2025</Cite></p>
    <p>La oportunidad de este trabajo consiste en unir generación, cálculo independiente, información identificable y control del profesional en una misma aplicación. El objeto de evaluación es el sistema asistido completo, incluido el tiempo que toma revisar y corregir sus propuestas.</p>
  </Section>;
}

export function ProblemAndObjectives() {
  return <Section id="problema" number="02" title="Problema y objetivos" lead="La necesidad de ahorrar trabajo solo justifica la innovación si el resultado conserva precisión, trazabilidad y control profesional.">
    <h3>Justificación: de la necesidad a la propuesta</h3>
    <p>La encuesta de 16 preguntas recogió respuestas de 13 profesionales: seis de nutrición clínica, tres de control de peso y estética, tres de nutrición deportiva y composición corporal, y uno de nutrición pediátrica. Entre las tareas tediosas destacan la redacción de recetas y listas de compra (46.2 %), la adaptación a preferencias (23.1 %), las equivalencias (15.4 %) y el ajuste de macronutrientes (15.4 %). Esta información orientó el diseño hacia un borrador editable y verificable. <Cite /></p>
    <figure className={styles.survey}>
      <figcaption>Figura 1. Necesidades y expectativas identificadas</figcaption>
      {survey.map(item => <div className={styles.surveyRow} key={item.label}>
        <div><span>{item.label}</span><strong>{item.percent.toFixed(1)} % <small>({item.count}/13)</small></strong></div>
        <div className={styles.barTrack} aria-hidden="true"><div style={{ width: `${item.percent}%` }} /></div>
      </div>)}
      <p className={styles.caption}>Fuente: síntesis de los porcentajes publicados en la Entrega 2. Frecuencias equivalentes sobre n = 13, redondeadas a una decimal. Cada barra corresponde a una pregunta distinta.</p>
    </figure>
    <p>Se trata de evidencia descriptiva de una muestra pequeña. No se documenta un muestreo probabilístico que permita generalizar los porcentajes a toda la población profesional. Tampoco debe confundirse esta encuesta de necesidades con la muestra, aún por definir, del estudio de evaluación del prototipo.</p>
    <Note title="Pregunta de investigación">
      <p>¿Puede un sistema que integra cálculo determinístico, fuentes recuperables y un LLM reducir el tiempo total de elaboración de planes dietéticos, manteniendo la calidad evaluada por el nutriólogo y su control sobre el resultado?</p>
    </Note>
    <h3>Objetivo general</h3>
    <p>Evaluar la contribución de un copiloto basado en LLM a la eficiencia de la planificación dietética, mediante la generación, revisión y corrección de borradores en un sistema web con datos estructurados, evidencia recuperable y supervisión profesional. Esta formulación operacionaliza el efecto esperado descrito en la Entrega 2.</p>
    <DataTable caption="Tabla 1. Objetivos específicos y evidencias para contrastarlos" headers={["Objetivo", "Evidencia prevista"]} rows={[
      ["Definir los requisitos del flujo profesional", "Encuesta, historias de usuario y criterios de aceptación."],
      ["Preparar una base de conocimiento con procedencia", "Manifiesto documental, registros BAM y fragmentos recuperados."],
      ["Delimitar las instrucciones y el alcance del agente", "Prompt versionado, restricciones y contrato de respuesta."],
      ["Desarrollar la interacción, integrar módulos y ejecutar un LLM local", "Flujo captura → cálculo → generación → revisión → exportación."],
      ["Comparar borradores con referencias profesionales", "Casos controlados y evaluación independiente de contenido."],
      ["Medir la reducción del tiempo total", "Tiempo manual y asistido, incluida la revisión y las correcciones."],
      ["Contrastar la meta de desviación ≤5 % en energía y macros", "Desviaciones por nutriente respecto a referencias definidas."],
      ["Contrastar la meta de más del 80 % con cambios menores", "Clasificación profesional de la magnitud de las modificaciones."],
    ]} />
    <p className={styles.caption}>Síntesis de los diez objetivos de la Entrega 2, pp. 8–9. Los porcentajes son metas de investigación; no son resultados observados.</p>
    <h3>Selección del prototipo</h3>
    <DataTable caption="Tabla 2. Comparación conceptual de alternativas" headers={["Alternativa", "Diseño", "Puntuación ponderada"]} rows={[
      ["A · LLM directo", "Generación basada en el conocimiento interno del modelo.", "2.30 / 5"],
      ["B · LLM + conocimiento", "Contexto especializado para respaldar la generación.", "4.25 / 5"],
      ["C · LLM + conocimiento + supervisión", "Borrador, cálculos, fuentes y revisión profesional explícita.", "4.85 / 5 · Seleccionado"],
    ]} />
    <p>La matriz asigna 20 % a precisión, 20 % a fundamento y trazabilidad, 15 % a personalización, 15 % a seguridad, 15 % a control profesional y 5 % a cada uno de los criterios de tiempo, usabilidad y viabilidad. La puntuación del prototipo C expresa una valoración conceptual del equipo, no una exactitud del 97 % ni un resultado experimental. <Cite id="ref-prototipo">Equipo 3033E, s. f.</Cite></p>
  </Section>;
}

export function Methodology() {
  return <Section id="metodologia" number="03" title="Metodología" lead="Design Thinking identifica la necesidad; Scrum organiza los incrementos; Lean Startup permite contrastar su valor.">
    <p>El proyecto articula comprensión del usuario, desarrollo iterativo y aprendizaje basado en evidencia. La Entrega 1 documenta la exploración y selección del prototipo; la Entrega 2 desarrolla la planificación con Scrum y Lean Startup. El plan metodológico no se presenta aquí como una certificación de que todos los eventos o experimentos hayan sido ejecutados. <Cite id="ref-entrega1">Equipo 3033E, 2026a</Cite> <Cite /></p>
    <h3>Design Thinking: comprender antes de construir</h3>
    <ol className={styles.steps}>
      <li><strong>Empatizar.</strong> Identificar tiempos, tareas repetitivas y preocupaciones mediante la encuesta a profesionales.</li>
      <li><strong>Definir.</strong> Delimitar el problema: producir un primer borrador útil conservando precisión y revisión profesional.</li>
      <li><strong>Idear.</strong> Contrastar generación directa, recuperación de conocimiento y supervisión explícita.</li>
      <li><strong>Prototipar.</strong> Seleccionar el prototipo C y materializar captura, cálculo, fuentes y edición.</li>
      <li><strong>Evaluar e iterar.</strong> Someter el flujo a casos controlados y retroalimentar el backlog; esta evaluación requiere todavía evidencia del piloto.</li>
    </ol>
    <h3>Scrum: responsabilidades e incrementos</h3>
    <p>La distribución documentada asigna a Adrián Lago Aponte la priorización del producto como Product Owner, a Esdras de la Torre Valdivia la facilitación como Scrum Master y a los tres integrantes el desarrollo, la integración, las pruebas y la documentación. La transparencia, inspección y adaptación sustentan el marco; las funciones se organizan en un Product Backlog, un Sprint Backlog y entregables incrementales. <Cite /> <Cite id="ref-scrum">Schwaber y Sutherland, 2020</Cite></p>
    <div className={styles.sprints} aria-label="Plan inicial de cuatro sprints">
      {[
        ["Sprint 1", "2 semanas", "Interfaz e integración del LLM"],
        ["Sprint 2", "1 semana", "Base de conocimiento y RAG"],
        ["Sprint 3", "1 semana", "Cálculos, restricciones y alertas"],
        ["Sprint 4", "2 semanas", "Edición, validación y pruebas"],
      ].map(([name, duration, title]) => <div key={name}><span>{duration}</span><strong>{name}</strong><p>{title}</p></div>)}
    </div>
    <p className={styles.caption}>Plan inicial de la Entrega 2, tabla 7. Las duraciones expresan planificación, no tiempos reales certificados.</p>
    <p>La planificación selecciona historias según prioridad y dependencias. La entrega propone puntos de control por chat los lunes, miércoles y viernes; es una adaptación del equipo, distinta del Daily Scrum diario del marco. La revisión del incremento contrasta criterios de aceptación y la retrospectiva debe convertir los impedimentos en acciones para la siguiente iteración. Jira concentra la planificación, GitHub el código y sus versiones, y Teams la coordinación.</p>
    <details className={styles.details}>
      <summary>Consultar el backlog inicial · 9 historias · 48 puntos</summary>
      <p>Los puntos siguen la escala de Fibonacci y representan esfuerzo relativo, incertidumbre y dependencias. No equivalen a horas ni a porcentaje de avance.</p>
      <DataTable caption="Tabla 3. Historias y criterios de aceptación resumidos" headers={["ID", "Historia", "Prioridad", "Puntos", "Criterio de aceptación"]} rows={backlog} />
      <p className={styles.caption}>Fuente: Entrega 2, tablas 8 y 9, pp. 35–37.</p>
    </details>
    <div className={styles.twoColumns}>
      <div><h4>Definition of Ready · lista para iniciar</h4><p>Historia redactada, criterios de aceptación definidos, datos disponibles y dependencias resueltas. Por ejemplo, la recuperación documental necesita documentos autorizados y un contrato de metadatos.</p></div>
      <div><h4>Definition of Done · terminada</h4><p>Código revisable, pruebas satisfactorias, cambios integrados en el repositorio y validación del Product Owner contra los objetivos. La evidencia del criterio acompaña al incremento.</p></div>
    </div>
    <h3>Lean Startup: convertir supuestos en aprendizaje</h3>
    <p>El ciclo construir–medir–aprender evita equiparar cantidad de funcionalidades con valor. La adaptación del equipo incorpora identificar la necesidad e iterar tras el aprendizaje. El MVP acota la inversión a las funciones necesarias para comprobar utilidad y confiabilidad. <Cite id="ref-lean">The Lean Startup, s. f.</Cite> <Cite /></p>
    <div className={styles.leanLoop}>
      <div><span>01</span><h4>Construir</h4><p>Un borrador editable con cálculos y fuentes identificables.</p></div>
      <div><span>02</span><h4>Medir</h4><p>Tiempo completo, desviaciones, correcciones y pertinencia de las fuentes.</p></div>
      <div><span>03</span><h4>Aprender</h4><p>Priorizar fallos observados y ajustar el siguiente incremento.</p></div>
    </div>
    <DataTable caption="Tabla 4. Hipótesis y decisiones de aprendizaje propuestas" headers={["Hipótesis", "Medición", "Decisión ante evidencia insuficiente"]} rows={[
      ["H1 · El borrador reduce trabajo", "Tiempo manual frente al asistido, incluyendo corrección.", "Revisar captura, latencia o calidad del borrador si la corrección elimina el ahorro."],
      ["H2 · El contenido es aprovechable", "Proporción de planes con cambios menores; meta >80 %.", "Ajustar prompts, datos y validadores si predominan reestructuraciones."],
      ["H3 · Las fuentes facilitan la revisión", "Respaldo real de recomendaciones en los fragmentos recuperados.", "Depurar corpus y recuperación si la fuente existe pero no sustenta la afirmación."],
    ]} />
    <Note title="Ejemplo: una necesidad atraviesa todo el método" tone="green">
      <p>La preocupación por cálculos incorrectos detectada en la encuesta se transforma en HU02: obtener cálculos desglosados. Scrum programa el motor de cálculo y su prueba manual; Lean mide si esa función reduce correcciones. Si el resultado falla, se revisan las reglas o los datos antes de ampliar funciones. Es un ejemplo de trazabilidad metodológica, no el reporte de un experimento ya realizado.</p>
    </Note>
  </Section>;
}
