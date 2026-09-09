"use client";
import { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { PatientWorkspace } from "../../../components/capture/patient-workspace";

function PatientPage() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const activeId = search.get("consultation");
  const confirmation = search.has("created") ? "Paciente creado." : search.has("saved") ? "Consulta guardada." : "";
  return <PatientWorkspace key={`${id}/${activeId || ""}`} id={id} activeId={activeId} confirmation={confirmation} />;
}
export default function Page() {
  return <Suspense fallback={<p className="p-8 text-sm text-slate-500">Cargando paciente…</p>}><PatientPage /></Suspense>;
}
