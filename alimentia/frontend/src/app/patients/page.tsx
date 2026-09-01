import React from "react";
import { Plus } from "lucide-react";
import Link from "next/link";

// --- TYPES & MOCK DATA ---

type PlanStatus = "EN REVISIÓN" | "PLAN APROBADO" | "BORRADOR" | "MODIFICADO";

interface PatientItem {
  id: string;
  patientName: string;
  patientId: string;
  age: number;
  objective: string;
  lastConsultation: string;
  planStatus: PlanStatus;
}

const PATIENTS_DATA: PatientItem[] = [
  {
    id: "1",
    patientName: "María González",
    patientId: "000045",
    age: 28,
    objective: "Pérdida de peso",
    lastConsultation: "25 ago 2026",
    planStatus: "EN REVISIÓN",
  },
  {
    id: "2",
    patientName: "Jorge Alcántara",
    patientId: "000044",
    age: 41,
    objective: "Mantenimiento",
    lastConsultation: "24 ago 2026",
    planStatus: "PLAN APROBADO",
  },
  {
    id: "3",
    patientName: "Lucía Ramírez",
    patientId: "000043",
    age: 34,
    objective: "Incremento de peso",
    lastConsultation: "24 ago 2026",
    planStatus: "BORRADOR",
  },
  {
    id: "4",
    patientName: "Ana Beltrán",
    patientId: "000042",
    age: 52,
    objective: "Pérdida de peso",
    lastConsultation: "22 ago 2026",
    planStatus: "PLAN APROBADO",
  },
  {
    id: "5",
    patientName: "Diego Márquez",
    patientId: "000041",
    age: 26,
    objective: "Incremento de peso",
    lastConsultation: "21 ago 2026",
    planStatus: "MODIFICADO",
  },
  {
    id: "6",
    patientName: "Sofía Herrera",
    patientId: "000040",
    age: 37,
    objective: "Mantenimiento",
    lastConsultation: "19 ago 2026",
    planStatus: "PLAN APROBADO",
  },
];

// --- MAIN COMPONENT ---

export default function PatientsPage() {
  return (
    <div className="flex-1 flex flex-col h-full bg-[#F8FAFC] overflow-hidden">
      {/* Topbar */}
      <header className="bg-white border-b border-slate-200 px-8 py-5 flex justify-between items-center flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Pacientes</h1>
          <p className="text-xs text-slate-500 mt-1">
            Adultos sin patologías clínicas complejas — alcance del MVP[cite: 1]
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors shadow-sm">
          <Plus size={16} /> Nuevo paciente
        </button>
      </header>

      {/* Contenido scrolleable */}
      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <div className="max-w-7xl mx-auto">
          {/* PATIENTS TABLE CONTAINER */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/50 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="py-3.5 px-6">Paciente</th>
                  <th className="py-3.5 px-6">Edad</th>
                  <th className="py-3.5 px-6">Objetivo</th>
                  <th className="py-3.5 px-6">Última consulta</th>
                  <th className="py-3.5 px-6">Estado del plan</th>
                  <th className="py-3.5 px-6 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
                {PATIENTS_DATA.map((patient) => (
                  <PatientRow key={patient.id} data={patient} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- HELPER COMPONENTS ---

function PatientRow({ data }: { data: PatientItem }) {
  const renderStatusBadge = (status: PlanStatus) => {
    switch (status) {
      case "EN REVISIÓN":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "PLAN APROBADO":
        return "bg-green-50 text-green-700 border-green-200";
      case "BORRADOR":
        return "bg-blue-50 text-blue-700 border-blue-200";
      case "MODIFICADO":
        return "bg-orange-50 text-orange-700 border-orange-200";
      default:
        return "bg-slate-50 text-slate-700 border-slate-200";
    }
  };

  return (
    <tr className="hover:bg-slate-50/50 transition-colors">
      {/* PATIENT NAME & ID */}
      <td className="py-4 px-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center font-bold text-slate-600 text-xs flex-shrink-0">
            {data.patientName
              .split(" ")
              .map((n) => n[0])
              .join("")
              .substring(0, 2)}
          </div>
          <div>
            <p className="font-semibold text-slate-800 text-sm">
              {data.patientName}
            </p>
            <p className="text-[10px] text-slate-400 font-mono">
              ID: {data.patientId}
            </p>
          </div>
        </div>
      </td>

      {/* AGE */}
      <td className="py-4 px-6 text-slate-600 text-sm">{data.age}</td>

      {/* OBJECTIVE */}
      <td className="py-4 px-6 text-slate-600 text-sm">{data.objective}</td>

      {/* LAST CONSULTATION */}
      <td className="py-4 px-6 text-slate-500 text-xs">
        {data.lastConsultation}
      </td>

      {/* STATUS */}
      <td className="py-4 px-6">
        <span
          className={`inline-block px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider border ${renderStatusBadge(data.planStatus)}`}
        >
          {data.planStatus}
        </span>
      </td>

      {/* ACTIONS */}
      <td className="py-4 px-6 text-right">
        {/* CAMBIO: Usamos Link y apuntamos a la ruta dinámica */}
        <Link
          href={`/patients/${data.id}`}
          className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg transition-colors shadow-sm inline-block"
        >
          Abrir
        </Link>
      </td>
    </tr>
  );
}
