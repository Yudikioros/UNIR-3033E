import type { ReactNode } from "react";
import styles from "./project.module.css";

export function Cite({ id = "ref-entrega2", children = "Equipo 3033E, 2026b" }: { id?: string; children?: ReactNode }) {
  return <a className={styles.citation} href={`#${id}`}>({children})</a>;
}

export function Section({ id, number, title, lead, children }: { id: string; number: string; title: string; lead: string; children: ReactNode }) {
  return <section id={id} className={styles.section} aria-labelledby={`${id}-title`}>
    <h2 id={`${id}-title`} tabIndex={-1}><span>{number}</span>{title}</h2>
    <p className={styles.lead}>{lead}</p>
    {children}
  </section>;
}

export function Note({ title, children, tone = "blue" }: { title: string; children: ReactNode; tone?: "blue" | "amber" | "green" }) {
  return <aside className={`${styles.note} ${styles[tone]}`}><strong>{title}</strong><div>{children}</div></aside>;
}

export function DataTable({ caption, headers, rows }: { caption: string; headers: string[]; rows: ReactNode[][] }) {
  return <div className={styles.tableScroll} role="region" aria-label={caption} tabIndex={0}>
    <table><caption>{caption}</caption><thead><tr>{headers.map(header => <th scope="col" key={header}>{header}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => cellIndex === 0 ? <th scope="row" key={cellIndex}>{cell}</th> : <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody>
    </table>
  </div>;
}
