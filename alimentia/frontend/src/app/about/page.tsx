import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Database, FileSearch, FileText, UserRound, ArrowUpRight, Menu } from "lucide-react";
import { team } from "../../components/about/content";
import { ProjectContents } from "../../components/about/interactives";
import { Introduction, Methodology, ProblemAndObjectives } from "../../components/about/research-chapters";
import { DataAndArchitecture, TechnicalDecisions } from "../../components/about/technical-chapters";
import { Conclusions, Evaluation, References } from "../../components/about/evaluation-chapters";
import styles from "../../components/about/project.module.css";

export const metadata: Metadata = {
  title: "Acerca del proyecto | AlimentIA · Equipo 3033E",
  description: "Fundamentos, metodología Scrum y Lean Startup, arquitectura RAG y evaluación del proyecto de investigación AlimentIA de la Maestría en Inteligencia Artificial de UNIR.",
};

export default function AboutProjectPage() {
  return <div className={styles.page} data-about-page>
    <header className={styles.header}>
      <div><Link href="/">AlimentIA</Link><span aria-hidden="true">/</span><span>Acerca del proyecto</span></div>
      <Link className={styles.prototypeLink} href="/patients">Ver prototipo <ArrowUpRight size={16} aria-hidden="true" /></Link>
      <details className={styles.mobileMenu}><summary aria-label="Navegación de AlimentIA"><Menu size={22} /></summary><nav aria-label="Navegación de la aplicación">
        {[["/", "Resumen"], ["/patients", "Pacientes"], ["/plans", "Planes"], ["/sources", "Fuentes"], ["/alerts", "Alertas"], ["/config", "Configuración"]].map(([href, title]) => <Link key={href} href={href}>{title}</Link>)}
      </nav></details>
    </header>
    <div id="about-scroll" className={styles.scroll}>
      <div id="project-top" className={styles.hero}>
        <div className={styles.heroTitle}>
          <h1>Inteligencia artificial,<br /><span>criterio humano.</span></h1>
          <div className={styles.heroFlow} aria-label="Datos, evidencia, borrador y revisión profesional">
            {[[Database, "Datos"], [FileSearch, "Evidencia"], [FileText, "Borrador"], [UserRound, "Revisión profesional"]].map(([Icon, title], index) => {
              const FlowIcon = Icon as typeof Database;
              return <div key={String(title)}><span><FlowIcon size={24} strokeWidth={1.5} aria-hidden="true" /></span><strong>{String(title)}</strong>{index < 3 ? <ArrowRight className={styles.flowArrow} size={18} aria-hidden="true" /> : null}</div>;
            })}
          </div>
        </div>
        <p className={styles.subtitle}>Planes dietéticos asistidos por modelos de lenguaje grande bajo supervisión de nutriólogos</p>
        <p className={styles.institution}>Maestría en Inteligencia Artificial · UNIR · Equipo 3033E</p>
      </div>
      <section className={styles.team} aria-labelledby="team-title">
        <h2 id="team-title">Equipo de investigación</h2>
        <ol>{team.map(person => <li key={person.name}><strong>{person.name}</strong><span>{person.role}</span></li>)}</ol>
      </section>
      <div className={styles.readingLayout}>
        <ProjectContents />
        <article className={styles.article} aria-label="Memoria del proyecto AlimentIA">
          <Introduction />
          <ProblemAndObjectives />
          <Methodology />
          <DataAndArchitecture />
          <TechnicalDecisions />
          <Evaluation />
          <Conclusions />
          <References />
        </article>
      </div>
    </div>
  </div>;
}
