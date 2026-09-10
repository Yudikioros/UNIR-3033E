"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, getPatient, getPatientConsultations, getConsultation, getCaptureOptions, errorMessage } from "../../services/api";
import type { Patient, Consultation, CaptureOptions } from "../../services/types";
import { PatientForm } from "./patient-form";
import { ConsultationForm } from "./consultation-form";
import { NutritionRequirements } from "./nutrition-requirements";
import { DietPlanDraft } from "./diet-plan-draft";
import { dateLabel, optionLabel, primaryButton, secondaryButton, Notice } from "./fields";

export function PatientWorkspace({ id, activeId, confirmation = "" }: { id: string; activeId: string | null; confirmation?: string }) {
  const router = useRouter();
  const [data, setData] = useState<{ patient: Patient; consultations: Consultation[]; options: CaptureOptions; active?: Consultation }>();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(confirmation);
  const [patientDirty, setPatientDirty] = useState(false);
  const [consultationDirty, setConsultationDirty] = useState(false);
  const dirty = patientDirty || consultationDirty;

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getPatient(id, controller.signal), getPatientConsultations(id, controller.signal), getCaptureOptions(controller.signal),
      activeId && activeId !== "new" ? getConsultation(activeId, controller.signal) : Promise.resolve(undefined)])
      .then(([patient, consultations, options, active]) => {
        if (active && active.patientId !== id) { setError("Esta consulta no pertenece al paciente seleccionado."); return; }
        setData({ patient, consultations, options, active });
      }).catch(err => {
        if (!controller.signal.aborted) setError(err instanceof ApiError && err.status === 404 ? "No se encontró el paciente o la consulta." : errorMessage(err, "No fue posible cargar los datos del paciente."));
      });
    return () => controller.abort();
  }, [id, activeId]);

  useEffect(() => {
    if (!dirty) return;
    const leave = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", leave);
    return () => window.removeEventListener("beforeunload", leave);
  }, [dirty]);

  function navigate(event: React.MouseEvent<HTMLAnchorElement>) {
    if (dirty) { event.preventDefault(); setNotice("Guarda los cambios pendientes antes de cambiar de consulta."); }
  }

  function patientSaved(patient: Patient) {
    setData(current => current ? { ...current, patient } : current);
    setNotice("Datos del paciente guardados.");
  }

  function consultationSaved(consultation: Consultation) {
    setNotice("Consulta guardada.");
    setData(current => current ? { ...current, active: consultation,
      consultations: [consultation, ...current.consultations.filter(c => c.id !== consultation.id)].sort((a, b) => b.consultationDate.localeCompare(a.consultationDate)) } : current);
    if (activeId !== consultation.id) router.replace(`/patients/${id}?consultation=${encodeURIComponent(consultation.id)}&saved=1`);
  }

  function calculated(consultation: Consultation) {
    setData(current => current ? { ...current, active: consultation,
      consultations: current.consultations.map(c => c.id === consultation.id ? consultation : c) } : current);
  }

  return <div className="flex h-full flex-1 flex-col overflow-hidden bg-[#F8FAFC]">
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-8 py-4">
      <div className="flex items-center gap-4"><Link href="/patients" aria-label="Volver a Pacientes" onClick={navigate} className="rounded-full p-2 text-slate-500 hover:bg-slate-100">←</Link><div>
        <h1 className="text-xl font-bold text-slate-800">{data ? `Paciente: ${data.patient.name}` : "Ficha del paciente"}</h1>
        <p className="mt-1 text-xs text-slate-500">Datos del paciente e historial de consultas</p>
      </div></div>
      {data ? <Link href={`/patients/${id}?consultation=new`} onClick={navigate} className={primaryButton}>Nueva consulta</Link> : null}
    </header>
    <div className="custom-scrollbar flex-1 overflow-y-auto p-8">
      {error ? <div className="space-y-4"><Notice error>{error}</Notice><button className={secondaryButton} onClick={() => window.location.reload()}>Reintentar</button><Link href="/patients" className="ml-4 text-sm text-blue-600">Volver a Pacientes</Link></div> : !data ? <p role="status" className="text-sm text-slate-500">Cargando paciente…</p> : <>
        {notice ? <div className="mb-5"><Notice>{notice}</Notice></div> : null}
        {dirty ? <p className="mb-4 text-xs text-amber-700">Hay cambios sin guardar.</p> : null}
        <div className="grid grid-cols-1 items-start gap-6 pb-8 xl:grid-cols-2">
          <div className="space-y-6">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-6 text-sm font-bold text-blue-600">1. Datos del paciente</h2>
              {data.patient.isDemo ? <p className="mb-4 text-xs text-blue-600">Caso demostrativo del MVP</p> : null}
              <PatientForm key={data.patient.updatedAt} patient={data.patient} options={data.options} onSaved={patientSaved} onDirtyChange={setPatientDirty} />
            </section>
            <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <h2 className="border-b border-slate-100 px-6 py-4 text-sm font-bold text-slate-700">Consultas</h2>
              <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-slate-50 text-slate-500"><tr>{["Fecha", "Peso", "Objetivo", "Estado", "Plan", ""].map(label => <th key={label} className="px-3 py-3 font-semibold">{label}</th>)}</tr></thead>
                <tbody className="divide-y divide-slate-100">{data.consultations.length ? data.consultations.map(consultation => <tr key={consultation.id} className={consultation.id === activeId ? "bg-blue-50/50" : ""}>
                  <td className="px-3 py-4">{dateLabel(consultation.consultationDate)}</td><td className="px-3 py-4">{consultation.weightKg !== null ? `${consultation.weightKg} kg` : "—"}</td>
                  <td className="px-3 py-4">{optionLabel(consultation.goal, data.options.goal)}</td><td className="px-3 py-4">{consultation.status === "READY" ? "Lista" : consultation.isEditable ? "En captura" : "Histórica"}</td>
                  <td className="px-3 py-4">{consultation.plans.length ? consultation.plans.map(plan => <span key={plan.id} className="block" title={plan.id}>Versión {plan.version}</span>) : "Sin plan"}</td>
                  <td className="px-3 py-4"><Link href={`/patients/${id}?consultation=${encodeURIComponent(consultation.id)}`} onClick={navigate} className="font-semibold text-blue-600 hover:underline">Abrir</Link></td>
                </tr>) : <tr><td colSpan={6} className="p-6 text-center text-slate-400">Todavía no hay consultas registradas.</td></tr>}</tbody></table></div>
            </section>
          </div>
          <div className="space-y-6">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-6 text-sm font-bold text-blue-600">2. Datos de la consulta actual</h2>
              {activeId ? <ConsultationForm key={data.active?.updatedAt || "new"} patient={data.patient} consultation={data.active} options={data.options} onSaved={consultationSaved} onDirtyChange={setConsultationDirty} /> : <div className="py-12 text-center text-sm text-slate-400">Abre una consulta del historial o selecciona Nueva consulta.</div>}
            </section>
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-6 text-sm font-bold text-blue-600">Requerimientos nutricionales</h2>
              <NutritionRequirements consultation={data.active} onCalculated={calculated} />
            </section>
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-6 text-sm font-bold text-blue-600">Plan dietético</h2>
              <DietPlanDraft key={data.active?.id || "none"} consultation={data.active}
                onGenerated={planId => router.push(`/plans/${planId}`)} />
            </section>
          </div>
        </div>
      </>}
    </div>
  </div>;
}
