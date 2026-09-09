"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Users, FileText, Clock, CheckCircle } from "lucide-react";
import { getDashboardSummary, getCaptureOptions, errorMessage } from "../services/api";
import type { CaptureOptions, DashboardPatientRow, DashboardPendingPlan, DashboardSummary, PlanStatus } from "../services/types";
import { Notice, dateLabel, optionLabel, secondaryButton, primaryButton } from "../components/capture/fields";

const PLAN_STATUS_LABELS: Record<PlanStatus, string> = {
  DRAFT: "Borrador", UNDER_REVIEW: "En revisión", MODIFIED: "Modificado",
  REGENERATED: "Regenerado", REJECTED: "Rechazado", APPROVED: "Aprobado",
};

function planStatusLabel(status: PlanStatus | null): string {
  return status ? PLAN_STATUS_LABELS[status] : "Sin plan";
}

// Sección 9: nunca redondea de forma engañosa (nunca "0 min" cuando no hay
// dato -eso lo resuelve `formatDuration` devolviendo "—"-, y siempre
// distingue horas de minutos en vez de mostrar solo minutos totales).
function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const totalMinutes = Math.round(seconds / 60);
  if (totalMinutes < 60) return `${totalMinutes} min`;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours} h ${String(minutes).padStart(2, "0")} min`;
}

export default function ResumenPage() {
  const [data, setData] = useState<{ summary: DashboardSummary; options: CaptureOptions }>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Nunca llama a setState de forma síncrona dentro de un efecto (solo en
  // callbacks de la promesa): la reactivación de "loading"/"error" para un
  // reintento la hace el manejador del botón, que sí es un evento real.
  const load = useCallback((signal?: AbortSignal) => {
    Promise.all([getDashboardSummary(signal), getCaptureOptions(signal)])
      .then(([summary, options]) => { if (!signal?.aborted) setData({ summary, options }); })
      .catch(err => { if (!signal?.aborted) setError(errorMessage(err, "No fue posible cargar el resumen.")); })
      .finally(() => { if (!signal?.aborted) setLoading(false); });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  function retry() {
    setLoading(true); setError("");
    load();
  }

  return <div className="flex h-full flex-1 flex-col overflow-hidden bg-[#F8FAFC]">
    <header className="shrink-0 border-b border-slate-200 bg-white px-8 py-5"><h1 className="text-2xl font-bold text-slate-800">Resumen</h1><p className="mt-1 text-xs text-slate-500">Actividad de tu consulta</p></header>
    <div className="custom-scrollbar flex-1 overflow-y-auto p-8"><div className="w-full space-y-6">
      {error ? (
        <div className="space-y-3">
          <Notice error>{error}</Notice>
          <button className={secondaryButton} onClick={retry}>Reintentar</button>
        </div>
      ) : (
        <>
          <MetricsRow summary={data?.summary} loading={loading} />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <section className="min-w-0 lg:col-span-2">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="font-bold text-slate-700">Pacientes registrados · más recientes primero</h2>
                <Link href="/patients" className="text-xs font-semibold text-blue-600 hover:underline">Ver todos</Link>
              </div>
              {loading || !data ? <TableSkeleton /> : <RecentPatientsTable patients={data.summary.recentPatients} options={data.options} />}
            </section>
            <div className="space-y-6">
              <PendingReviewPanel loading={loading} pendingPlans={data?.summary.pendingPlans} />
              <div className="rounded-2xl border border-blue-100 bg-blue-50/50 p-5">
                <h2 className="mb-2 text-xs font-bold uppercase tracking-wide text-blue-800">Principio del sistema</h2>
                <p className="text-xs leading-relaxed text-blue-700/80">AlimentIA prepara y propone. El nutriólogo revisa y decide. Ningún plan se considera válido sin aprobación explícita del profesional responsable.</p>
              </div>
            </div>
          </div>
        </>
      )}
    </div></div>
  </div>;
}

function MetricCard({ icon: Icon, label, value, hint }: { icon: typeof Users; label: string; value: string; hint?: string }) {
  return <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="mb-2 flex items-center gap-2 text-blue-600"><Icon size={16} /><h2 className="text-xs font-semibold text-slate-600">{label}</h2></div>
    <p className="text-3xl font-bold text-slate-800">{value}</p>
    {hint ? <p className="mt-1 text-[10px] text-slate-400">{hint}</p> : null}
  </div>;
}

function MetricCardSkeleton() {
  return <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="mb-3 h-4 w-24 animate-pulse rounded bg-slate-100" />
    <div className="h-8 w-12 animate-pulse rounded bg-slate-200" />
  </div>;
}

function MetricsRow({ summary, loading }: { summary?: DashboardSummary; loading: boolean }) {
  if (loading || !summary) {
    return <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-5">
      {Array.from({ length: 5 }).map((_, index) => <MetricCardSkeleton key={index} />)}
    </div>;
  }
  const { metrics } = summary;
  return <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-5">
    <MetricCard icon={Users} label="Pacientes registrados" value={String(metrics.registeredPatients)} hint="Registros guardados" />
    <MetricCard icon={FileText} label="Planes generados" value={String(metrics.generatedPlans)} hint="Todas las versiones" />
    <MetricCard icon={Clock} label="Pendientes de revisión" value={String(metrics.pendingReview)} hint="Última versión por consulta" />
    <MetricCard icon={CheckCircle} label="Planes aprobados" value={String(metrics.approvedPlans)} hint="Última versión por consulta" />
    <MetricCard icon={Clock} label="Tiempo promedio" value={formatDuration(metrics.averageReviewTimeSeconds)} hint="Generación → aprobación" />
  </div>;
}

function TableSkeleton() {
  return <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    {Array.from({ length: 4 }).map((_, index) => (
      <div key={index} className="flex items-center gap-4 border-b border-slate-100 px-6 py-4 last:border-0">
        <div className="h-9 w-9 animate-pulse rounded-full bg-slate-100" />
        <div className="h-3 w-32 animate-pulse rounded bg-slate-100" />
        <div className="ml-auto h-3 w-20 animate-pulse rounded bg-slate-100" />
      </div>
    ))}
  </div>;
}

function RecentPatientsTable({ patients, options }: { patients: DashboardPatientRow[]; options: CaptureOptions }) {
  return <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm"><table className="w-full border-collapse text-left">
    <thead><tr className="border-b border-slate-200 bg-slate-50/50 text-xs font-semibold uppercase tracking-wider text-slate-500">
      {["Paciente", "Edad", "Objetivo", "Últ. consulta", "Estado del plan", "Acciones"].map(label => <th key={label} className="px-6 py-3.5">{label}</th>)}
    </tr></thead><tbody className="divide-y divide-slate-100 text-sm text-slate-700">
      {!patients.length ? <tr><td colSpan={6} className="px-6 py-8 text-center text-slate-400">No hay pacientes registrados aún.</td></tr> : patients.map(patient => <tr key={patient.id} className="hover:bg-slate-50/50">
        <td className="px-6 py-4"><div className="flex items-center gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold uppercase text-slate-600">{patient.name.slice(0, 2)}</div><div>
          <p className="font-semibold text-slate-800">{patient.name}</p><p className="font-mono text-[10px] text-slate-400">ID: {patient.id.split("-")[0]}</p>
          {patient.isDemo ? <span className="text-[10px] text-blue-600">Caso demostrativo</span> : null}
        </div></div></td>
        <td className="px-6 py-4">{patient.currentAge ?? "—"}</td>
        <td className="px-6 py-4">{patient.goal ? optionLabel(patient.goal, options.goal) : "—"}</td>
        <td className="px-6 py-4 text-xs text-slate-500">{patient.latestConsultationDate ? dateLabel(patient.latestConsultationDate) : "—"}</td>
        <td className="px-6 py-4"><span className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs">{planStatusLabel(patient.latestPlanStatus)}</span></td>
        <td className="px-6 py-4"><Link href={`/patients/${patient.id}`} className={secondaryButton}>Abrir</Link></td>
      </tr>)}
    </tbody></table></div>;
}

function PendingReviewPanel({ loading, pendingPlans }: { loading: boolean; pendingPlans?: DashboardPendingPlan[] }) {
  return <section className="overflow-hidden rounded-2xl border border-orange-200 bg-white shadow-sm">
    <div className="flex items-center justify-between border-b border-slate-100 bg-orange-50/30 p-4">
      <h2 className="text-sm font-bold text-orange-800">Pendientes de revisión</h2>
      <Link href="/plans" className="text-xs font-semibold text-blue-600 hover:underline">Ver todos</Link>
    </div>
    {loading || !pendingPlans ? (
      <div className="space-y-3 p-5">
        {Array.from({ length: 2 }).map((_, index) => <div key={index} className="h-12 animate-pulse rounded-lg bg-slate-100" />)}
      </div>
    ) : pendingPlans.length === 0 ? (
      <p className="p-5 text-xs text-slate-500">No hay planes pendientes de revisión.</p>
    ) : (
      <ul className="divide-y divide-slate-100">
        {pendingPlans.map(plan => <li key={plan.planId} className="flex items-center justify-between gap-3 p-4">
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold text-slate-800">{plan.patientName}</p>
            <p className="text-[11px] text-slate-500">Versión {plan.version} · {planStatusLabel(plan.status)}</p>
            <p className="text-[10px] text-slate-400">Generado: {plan.generatedAt ? dateLabel(plan.generatedAt) : "—"}</p>
          </div>
          <Link href={`/plans/${plan.planId}`} className={`${primaryButton} shrink-0 px-3 py-1.5 text-xs`}>Abrir</Link>
        </li>)}
      </ul>
    )}
  </section>;
}
