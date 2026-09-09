"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { getPatients, getCaptureOptions, errorMessage } from "../../services/api";
import type { Patient, CaptureOptions } from "../../services/types";
import { PatientTable } from "../../components/capture/patient-table";
import { Notice, primaryButton, secondaryButton } from "../../components/capture/fields";

export default function PatientsPage() {
  const [data, setData] = useState<{ patients: Patient[]; options: CaptureOptions }>();
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getPatients(controller.signal), getCaptureOptions(controller.signal)])
      .then(([patients, options]) => setData({ patients, options }))
      .catch(err => { if (!controller.signal.aborted) setError(errorMessage(err, "No fue posible cargar los pacientes.")); });
    return () => controller.abort();
  }, []);
  return <div className="flex h-full flex-1 flex-col overflow-hidden bg-[#F8FAFC]">
    <header className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-8 py-5">
      <div><h1 className="text-2xl font-bold text-slate-800">Pacientes</h1><p className="mt-1 text-xs text-slate-500">Adultos sin patologías clínicas complejas — alcance del MVP</p></div>
      <Link href="/patients/new" className={primaryButton}><Plus size={16} /> Nuevo paciente</Link>
    </header>
    <div className="custom-scrollbar flex-1 overflow-y-auto p-8"><div className="mx-auto max-w-7xl">
      {error ? <div className="space-y-4"><Notice error>{error}</Notice><button className={secondaryButton} onClick={() => window.location.reload()}>Reintentar</button></div> : data ? <PatientTable patients={data.patients} options={data.options} /> : <p role="status" className="py-8 text-center text-sm text-slate-400">Cargando pacientes…</p>}
    </div></div>
  </div>;
}
