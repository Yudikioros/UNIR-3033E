"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowRight, CheckCircle2, CircleAlert } from "lucide-react";
import { chapters } from "./content";
import styles from "./project.module.css";

export function ProjectContents() {
  const [active, setActive] = useState<string>("introduccion");
  useEffect(() => {
    const root = document.getElementById("about-scroll");
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.isIntersecting) setActive(entry.target.id.replace(/-title$/, ""));
      }
    }, { root, rootMargin: "-5% 0px -65% 0px", threshold: 0 });
    for (const chapter of chapters) {
      const heading = document.getElementById(`${chapter.id}-title`);
      if (heading) observer.observe(heading);
    }
    return () => observer.disconnect();
  }, []);
  return <nav className={styles.contents} aria-label="Contenido del proyecto">
    <p>Contenido</p>
    <ol>{chapters.map((chapter, index) => <li key={chapter.id}>
      <a href={`#${chapter.id}`} onClick={() => setActive(chapter.id)} aria-current={active === chapter.id ? "location" : undefined}>
        <span>{String(index + 1).padStart(2, "0")}</span>{chapter.title}
      </a>
    </li>)}</ol>
    <a className={styles.backTop} href="#project-top">Volver al inicio ↑</a>
  </nav>;
}

const stages = [
  { label: "Captura", title: "Datos estructurados desde el origen", description: "El profesional registra paciente, consulta, medidas, actividad, objetivo, preferencias y restricciones. La validación de campos y rangos técnicos detecta entradas incompletas antes del cálculo.", left: ["Contrato de entrada", "FastAPI y esquemas Pydantic definen los campos. Paciente y consulta se almacenan por separado para conservar el contexto de cada encuentro."], right: ["Límite", "Una captura válida no confirma que el caso sea clínicamente adecuado para el MVP. El alcance debe comprobarlo el profesional."] },
  { label: "Cálculo", title: "Una base numérica reproducible", description: "El motor determinístico usa Mifflin–St Jeor, un factor de actividad y reglas de objetivo versionadas. El LLM recibe esos resultados como restricciones del borrador.", left: ["Qué se conserva", "Método, versión de reglas, fecha y métricas del cálculo; una misma entrada bajo las mismas reglas produce el mismo resultado."], right: ["Límite", "Las distribuciones de macronutrientes y ajustes del MVP son reglas configuradas, no una validación clínica universal."] },
  { label: "BAM + RAG", title: "Dos fuentes, dos funciones", description: "El sistema combina recuperación tabular de composición alimentaria y recuperación semántica de documentos. Ambas aportan contexto, pero resuelven problemas distintos.", left: ["BAM · Datos tabulares", "Registros nutricionales con código, nombre y versión. Una coincidencia exacta normalizada permite sustituir valores generados cuando la porción está expresada en gramos."], right: ["RAG · Evidencia documental", "Fragmentos de fuentes autorizadas recuperados con embeddings y Qdrant. Se conserva identidad de la fuente, contenido recuperado y puntuación de similitud."] },
  { label: "LLM local", title: "Generación acotada al contexto", description: "Un prompt reúne el perfil, los requerimientos calculados, los alimentos recuperados y los fragmentos documentales. Ollama sirve el modelo local para producir una estructura de comidas y alimentos.", left: ["Configuración de referencia", "Docker Compose configura llama3.2:3b, temperatura 0.2 y timeout de 240 segundos por defecto. Son parámetros del prototipo, no un resultado de optimización experimental."], right: ["Trazabilidad", "Se registra el intento de generación, modelo, versión del prompt y duración. Cambiar de modelo exige volver a evaluar su comportamiento."] },
  { label: "Validación", title: "Comprobar antes de aprobar", description: "Pydantic comprueba la estructura de la respuesta. Las reglas deterministas examinan comidas, cantidades, restricciones declaradas y desviaciones energéticas y de macronutrientes.", left: ["Reglas actuales", "La tolerancia energética es ±5 %; para macronutrientes es ±10 % cuando existen datos y objetivos completos. Los errores bloqueantes impiden la aprobación."], right: ["Límite", "La búsqueda de términos restringidos no detecta todos los sinónimos o interacciones. Los datos no verificados contra BAM y la ausencia de RAG se comunican, pero no equivalen siempre a un bloqueo."] },
  { label: "Revisión", title: "La decisión final es profesional", description: "El nutriólogo revisa, modifica, regenera, aprueba o rechaza el borrador. La aplicación conserva versiones y cambios, y permite exportar el plan conforme al flujo de aprobación.", left: ["Human-in-the-loop", "La intervención humana forma parte del sistema evaluado. El tiempo de revisión debe incluirse al comparar el proceso manual con el asistido."], right: ["Evidencia", "El historial vincula consulta, plan, generaciones, fuentes, validaciones y cambios. La calidad clínica requiere una evaluación externa al propio modelo."] },
];

export function ArchitectureExplorer() {
  const [selected, setSelected] = useState(2);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  function onKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number;
    if (event.key === "ArrowRight") next = (index + 1) % stages.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + stages.length) % stages.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = stages.length - 1;
    else return;
    event.preventDefault(); setSelected(next); tabs.current[next]?.focus();
  }
  const stage = stages[selected];
  return <figure className={styles.architecture}>
    <figcaption>Figura 2. Recorrido técnico del prototipo <span>Selecciona una etapa para explorarla.</span></figcaption>
    <div className={styles.pipeline} role="tablist" aria-label="Etapas de la arquitectura">
      {stages.map((step, index) => <button key={step.label} ref={element => { tabs.current[index] = element; }} type="button" role="tab" id={`stage-${index}`} aria-controls="stage-panel" aria-selected={selected === index} tabIndex={selected === index ? 0 : -1} onClick={() => setSelected(index)} onKeyDown={event => onKey(event, index)}>
        <span>{String(index + 1).padStart(2, "0")}</span><strong>{step.label}</strong>{index < stages.length - 1 ? <ArrowRight size={14} aria-hidden="true" /> : null}
      </button>)}
    </div>
    <div id="stage-panel" role="tabpanel" aria-labelledby={`stage-${selected}`} tabIndex={0} className={styles.stagePanel}>
      <h3>{stage.title}</h3><p>{stage.description}</p>
      <div className={styles.twoColumns}>{[stage.left, stage.right].map(([title, text]) => <div key={title}><h4>{title}</h4><p>{text}</p></div>)}</div>
    </div>
    <p className={styles.caption}>Fuente: elaboración propia a partir del código del prototipo. La recuperación aporta contexto; la revisión profesional determina su pertinencia.</p>
  </figure>;
}

export function ValidationExample() {
  const [calories, setCalories] = useState(2040);
  const [restricted, setRestricted] = useState(false);
  const deviation = Math.abs(calories - 2000) / 2000 * 100;
  const blocked = deviation > 5 || restricted;
  return <div className={styles.example}>
    <h3>Ejemplo interactivo: una regla verificable</h3>
    <p>Caso sintético con objetivo de 2,000 kcal. Modifica la energía del borrador para observar la regla de tolerancia del prototipo.</p>
    <label htmlFor="example-energy">Energía del borrador <strong>{calories.toLocaleString("es-MX")} kcal</strong></label>
    <input id="example-energy" type="range" min={1800} max={2200} step={10} value={calories} onChange={event => setCalories(Number(event.target.value))} aria-valuetext={`${calories} kilocalorías`} />
    <div className={styles.rangeLabels}><span>1,800 kcal</span><span>Objetivo: 2,000 kcal</span><span>2,200 kcal</span></div>
    <label className={styles.checkLabel}><input type="checkbox" checked={restricted} onChange={event => setRestricted(event.target.checked)} />Simular coincidencia con un alimento restringido</label>
    <div className={`${styles.exampleResult} ${blocked ? styles.resultBlocked : styles.resultPass}`} role="status" aria-live="polite">
      {blocked ? <CircleAlert size={22} aria-hidden="true" /> : <CheckCircle2 size={22} aria-hidden="true" />}
      <div><strong>{blocked ? "Se impediría la aprobación" : "Cumple esta comprobación energética"}</strong><p>Desviación absoluta: {deviation.toFixed(1)} %. {restricted ? "Existe una coincidencia con una restricción declarada." : deviation > 5 ? "Supera el margen de ±5 %." : "Aún requiere las demás validaciones y revisión profesional."}</p></div>
    </div>
    <p className={styles.caption}>Demostración local de dos reglas; no envía datos a la API, no crea planes y no acredita seguridad clínica.</p>
  </div>;
}
