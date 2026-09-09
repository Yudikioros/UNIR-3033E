import Link from "next/link";
import type { CaptureOptions, Patient, PlanStatus } from "../../services/types";
import { dateLabel, optionLabel, secondaryButton } from "./fields";

const planLabels: Record<PlanStatus, string> = { DRAFT: "Borrador", UNDER_REVIEW: "En revisión", MODIFIED: "Modificado", REGENERATED: "Regenerado", REJECTED: "Rechazado", APPROVED: "Aprobado" };

export function PatientTable({ patients, options }: { patients: Patient[]; options: CaptureOptions }) {
  return <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm"><table className="w-full border-collapse text-left">
    <thead><tr className="border-b border-slate-200 bg-slate-50/50 text-xs font-semibold uppercase tracking-wider text-slate-500">
      {["Paciente", "Edad", "Objetivo", "Últ. consulta", "Estado del plan", "Acciones"].map(label => <th key={label} className="px-6 py-3.5">{label}</th>)}
    </tr></thead><tbody className="divide-y divide-slate-100 text-sm text-slate-700">
      {!patients.length ? <tr><td colSpan={6} className="px-6 py-8 text-center text-slate-400">No hay pacientes registrados aún.</td></tr> : patients.map(patient => <tr key={patient.id} className="hover:bg-slate-50/50">
        <td className="px-6 py-4"><div className="flex items-center gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold uppercase text-slate-600">{patient.name.slice(0, 2)}</div><div>
          <p className="font-semibold text-slate-800">{patient.name}</p><p className="font-mono text-[10px] text-slate-400">ID: {patient.id.split("-")[0]}</p>
          {patient.isDemo ? <span className="text-[10px] text-blue-600">Caso demostrativo</span> : null}
        </div></div></td>
        <td className="px-6 py-4">{patient.currentAge ?? "—"}</td><td className="px-6 py-4">{optionLabel(patient.defaultGoal, options.goal)}</td>
        <td className="px-6 py-4 text-xs text-slate-500">{dateLabel(patient.latestConsultationDate)}</td>
        <td className="px-6 py-4"><span className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs">{patient.latestPlan ? planLabels[patient.latestPlan.status] : "Sin plan"}</span></td>
        <td className="px-6 py-4"><Link href={`/patients/${patient.id}`} className={secondaryButton}>Abrir</Link></td>
      </tr>)}
    </tbody></table></div>;
}
