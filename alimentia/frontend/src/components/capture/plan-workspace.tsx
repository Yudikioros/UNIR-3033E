"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, getPlan, getConsultation, getPatient, errorMessage } from "../../services/api";
import type { Consultation, DietPlanDetail, Patient } from "../../services/types";
import { DietPlanDraft } from "./diet-plan-draft";
import { secondaryButton, Notice } from "./fields";

export function PlanWorkspace({ id }: { id: string }) {
  const [data, setData] = useState<{ plan: DietPlanDetail; consultation: Consultation; patient: Patient }>();
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getPlan(id, controller.signal)
      .then(async plan => {
        const consultation = await getConsultation(plan.consultationId, controller.signal);
        const patient = await getPatient(consultation.patientId, controller.signal);
        if (!controller.signal.aborted) setData({ plan, consultation, patient });
      })
      .catch(err => {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError && err.status === 404
          ? "No se encontró el plan solicitado." : errorMessage(err, "No fue posible cargar el plan."));
      });
    return () => controller.abort();
  }, [id]);

  return <div className="flex h-full flex-1 flex-col overflow-hidden bg-[#F8FAFC]">
    <header className="flex shrink-0 items-center gap-4 border-b border-slate-200 bg-white px-8 py-4">
      <Link href="/plans" aria-label="Volver a Planes" className="rounded-full p-2 text-slate-500 hover:bg-slate-100">←</Link>
      <div>
        <h1 className="text-xl font-bold text-slate-800">{data ? `Plan de ${data.patient.name}` : "Plan nutricional"}</h1>
        <p className="mt-1 text-xs text-slate-500">{data ? `Consulta del ${new Date(data.consultation.consultationDate).toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" })} · Versión ${data.plan.version}` : "Cargando…"}</p>
      </div>
    </header>
    <div className="custom-scrollbar flex-1 overflow-y-auto p-8">
      {error ? <div className="space-y-4">
        <Notice error>{error}</Notice>
        <div className="flex gap-3">
          <button className={secondaryButton} onClick={() => window.location.reload()}>Reintentar</button>
          <Link href="/plans" className="text-sm text-blue-600 hover:underline">Volver a Planes</Link>
        </div>
      </div> : !data ? <p role="status" className="text-sm text-slate-500">Cargando plan…</p> : <>
        <div className="mx-auto max-w-4xl space-y-6 pb-8">
          <DietPlanDraft consultation={data.consultation} initialPlanId={id} />
        </div>
      </>}
    </div>
  </div>;
}
