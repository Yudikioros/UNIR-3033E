"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getCaptureOptions, errorMessage } from "../../../services/api";
import type { CaptureOptions } from "../../../services/types";
import { PatientForm } from "../../../components/capture/patient-form";
import { Notice, secondaryButton } from "../../../components/capture/fields";

export default function NewPatientPage() {
  const router = useRouter();
  const [options, setOptions] = useState<CaptureOptions>();
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    getCaptureOptions(controller.signal).then(setOptions).catch(err => {
      if (!controller.signal.aborted) setError(errorMessage(err, "No fue posible cargar el formulario."));
    });
    return () => controller.abort();
  }, []);
  return <div className="flex h-full flex-1 flex-col overflow-hidden bg-[#F8FAFC]">
    <header className="flex shrink-0 items-center gap-4 border-b border-slate-200 bg-white px-8 py-5"><Link href="/patients" className={secondaryButton}>← Pacientes</Link><h1 className="text-2xl font-bold text-slate-800">Nuevo paciente</h1></header>
    <div className="custom-scrollbar flex-1 overflow-y-auto p-8"><section className="max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <p className="mb-6 text-xs text-slate-500">Registra sus datos básicos. Las medidas se capturan después en una consulta.</p>
      {error ? <Notice error>{error}</Notice> : options ? <PatientForm options={options} onSaved={patient => router.replace(`/patients/${patient.id}?created=1`)} /> : <p role="status" className="text-sm text-slate-500">Cargando formulario…</p>}
    </section></div>
  </div>;
}
