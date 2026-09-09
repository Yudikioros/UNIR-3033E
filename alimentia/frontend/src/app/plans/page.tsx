"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getPatients, getPatientConsultations, getConsultationPlans, downloadPlanPdf, errorMessage } from "../../services/api";
import type { DietPlanDetail, PlanStatus } from "../../services/types";
import { dateLabel, Notice } from "../../components/capture/fields";

interface PlanRow extends DietPlanDetail {
  patientName: string;
}

const STATUS_STYLE: Record<PlanStatus, string> = {
  DRAFT: "bg-amber-50 text-amber-700 border-amber-200",
  UNDER_REVIEW: "bg-amber-50 text-amber-700 border-amber-200",
  MODIFIED: "bg-amber-50 text-amber-700 border-amber-200",
  REGENERATED: "bg-amber-50 text-amber-700 border-amber-200",
  APPROVED: "bg-green-50 text-green-700 border-green-200",
  REJECTED: "bg-red-50 text-red-700 border-red-200",
};
const STATUS_LABEL: Record<PlanStatus, string> = {
  DRAFT: "BORRADOR", UNDER_REVIEW: "EN REVISIÓN", MODIFIED: "MODIFICADO",
  REGENERATED: "REGENERADO", APPROVED: "APROBADO", REJECTED: "RECHAZADO",
};
const EDITABLE_STATUSES: PlanStatus[] = ["DRAFT", "UNDER_REVIEW"];

function energyLabel(plan: DietPlanDetail): string {
  if (plan.totalCalories != null) return `${Math.round(plan.totalCalories)} kcal`;
  if (plan.targetCalories != null) return `≈ ${Math.round(plan.targetCalories)} kcal (objetivo)`;
  return "—";
}

export default function PlanesPage() {
  const [rows, setRows] = useState<PlanRow[]>();
  const [loadError, setLoadError] = useState("");
  const [exportingId, setExportingId] = useState<string>();
  const [exportError, setExportError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const patients = await getPatients(controller.signal);
        const collected: PlanRow[] = [];
        for (const patient of patients) {
          const consultations = await getPatientConsultations(patient.id, controller.signal);
          for (const consultation of consultations) {
            if (!consultation.plans.length) continue;
            const plans = await getConsultationPlans(consultation.id, controller.signal);
            for (const plan of plans) collected.push({ ...plan, patientName: patient.name });
          }
        }
        collected.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
        if (!controller.signal.aborted) setRows(collected);
      } catch (err) {
        if (!controller.signal.aborted) setLoadError(errorMessage(err, "No fue posible cargar los planes."));
      }
    }
    load();
    return () => controller.abort();
  }, []);

  async function onExport(planId: string) {
    if (exportingId) return;
    setExportingId(planId); setExportError("");
    try {
      await downloadPlanPdf(planId);
    } catch (err) {
      setExportError(errorMessage(err, "No fue posible exportar el plan a PDF."));
    } finally {
      setExportingId(undefined);
    }
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F8FAFC] overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-8 py-5 flex justify-between items-center flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">
            Planes Nutricionales
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Historial de dietas generadas y aprobadas en el sistema
          </p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <div className="max-w-7xl mx-auto space-y-4">
          {exportError ? <Notice error>{exportError}</Notice> : null}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/50 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="py-3.5 px-6">ID Plan</th>
                  <th className="py-3.5 px-6">Paciente</th>
                  <th className="py-3.5 px-6">Energía</th>
                  <th className="py-3.5 px-6">Fecha Generación</th>
                  <th className="py-3.5 px-6">Estado</th>
                  <th className="py-3.5 px-6">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
                {loadError ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8">
                      <Notice error>{loadError}</Notice>
                    </td>
                  </tr>
                ) : rows === undefined ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-slate-400">
                      Cargando planes...
                    </td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-slate-400">
                      No hay planes generados aún.
                    </td>
                  </tr>
                ) : (
                  rows.map((plan) => (
                    <tr key={plan.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="py-4 px-6 font-mono text-xs text-slate-400" title={plan.id}>
                        {plan.id.split("-")[0]}
                      </td>
                      <td className="py-4 px-6 font-semibold text-slate-800">
                        {plan.patientName}
                      </td>
                      <td className="py-4 px-6 text-slate-600 font-mono text-xs">
                        {energyLabel(plan)}
                      </td>
                      <td className="py-4 px-6 text-slate-500 text-xs">
                        {dateLabel(plan.generatedAt || plan.createdAt)}
                      </td>
                      <td className="py-4 px-6">
                        <span className={`inline-block px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider border ${STATUS_STYLE[plan.status]}`}>
                          {STATUS_LABEL[plan.status]} · v{plan.version}
                        </span>
                      </td>
                      <td className="py-4 px-6">
                        <div className="flex flex-wrap items-center gap-3">
                          <Link href={`/plans/${plan.id}`} className="text-xs font-semibold text-blue-600 hover:underline">Ver</Link>
                          {EDITABLE_STATUSES.includes(plan.status) ? (
                            <Link href={`/plans/${plan.id}`} className="text-xs font-semibold text-slate-500 hover:text-slate-700">Editar</Link>
                          ) : null}
                          {plan.status === "APPROVED" ? (
                            <button
                              className="text-xs font-semibold text-slate-500 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                              onClick={() => onExport(plan.id)}
                              disabled={exportingId === plan.id}
                            >
                              {exportingId === plan.id ? "Exportando…" : "Exportar PDF"}
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
