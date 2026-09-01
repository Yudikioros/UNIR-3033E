"use client";

import React, { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import Link from "next/link";
import { getPatients } from "../../services/api";

export default function PatientsPage() {
  const [patients, setPatients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const data = await getPatients();
        setPatients(data);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F8FAFC] overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-8 py-5 flex justify-between items-center flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Pacientes</h1>
          <p className="text-xs text-slate-500 mt-1">
            Adultos sin patologías clínicas complejas — alcance del MVP
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors shadow-sm">
          <Plus size={16} /> Nuevo paciente
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/50 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="py-3.5 px-6">Paciente</th>
                  <th className="py-3.5 px-6">Edad</th>
                  <th className="py-3.5 px-6">Objetivo</th>
                  <th className="py-3.5 px-6">Fecha Registro</th>
                  <th className="py-3.5 px-6">Estado del plan</th>
                  <th className="py-3.5 px-6 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-slate-400">
                      Cargando pacientes...
                    </td>
                  </tr>
                ) : patients.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-slate-400">
                      No hay pacientes registrados aún.
                    </td>
                  </tr>
                ) : (
                  patients.map((patient) => (
                    <PatientRow key={patient.id} data={patient} />
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

function PatientRow({ data }: { data: any }) {
  // Tomamos el estado del último plan generado, si existe
  const latestPlanStatus =
    data.plans && data.plans.length > 0 ? data.plans[0].status : "SIN PLAN";

  // Formateamos la fecha de creación a DD/MM/YYYY
  const formattedDate = new Date(data.createdAt).toLocaleDateString("es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });

  const renderStatusBadge = (status: string) => {
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
        return "bg-slate-100 text-slate-600 border-slate-300";
    }
  };

  return (
    <tr className="hover:bg-slate-50/50 transition-colors">
      <td className="py-4 px-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center font-bold text-slate-600 text-xs flex-shrink-0 uppercase">
            {data.name.substring(0, 2)}
          </div>
          <div>
            <p className="font-semibold text-slate-800 text-sm">{data.name}</p>
            <p className="text-[10px] text-slate-400 font-mono">
              ID: {data.id.split("-")[0]}
            </p>
          </div>
        </div>
      </td>
      <td className="py-4 px-6 text-slate-600 text-sm">{data.age}</td>
      <td className="py-4 px-6 text-slate-600 text-sm">{data.goal}</td>
      <td className="py-4 px-6 text-slate-500 text-xs">{formattedDate}</td>
      <td className="py-4 px-6">
        <span
          className={`inline-block px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider border ${renderStatusBadge(latestPlanStatus)}`}
        >
          {latestPlanStatus}
        </span>
      </td>
      <td className="py-4 px-6 text-right">
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
