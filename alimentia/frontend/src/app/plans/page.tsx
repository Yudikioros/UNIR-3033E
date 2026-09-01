"use client";

import React, { useEffect, useState } from "react";
import { getPlans } from "../../services/api";

export default function PlanesPage() {
  const [planes, setPlanes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const data = await getPlans();
        setPlanes(data);
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
          <h1 className="text-2xl font-bold text-slate-800">
            Planes Nutricionales
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Historial de dietas generadas y aprobadas en el sistema
          </p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <div className="max-w-7xl mx-auto bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/50 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                <th className="py-3.5 px-6">ID Plan</th>
                <th className="py-3.5 px-6">Paciente</th>
                <th className="py-3.5 px-6">Energía (TDEE)</th>
                <th className="py-3.5 px-6">Fecha Generación</th>
                <th className="py-3.5 px-6">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-slate-400">
                    Cargando planes...
                  </td>
                </tr>
              ) : planes.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-slate-400">
                    No hay planes generados aún.
                  </td>
                </tr>
              ) : (
                planes.map((plan) => {
                  const formattedDate = new Date(
                    plan.createdAt,
                  ).toLocaleDateString("es-MX", {
                    day: "2-digit",
                    month: "short",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  });
                  return (
                    <tr
                      key={plan.id}
                      className="hover:bg-slate-50/50 transition-colors cursor-pointer"
                    >
                      <td className="py-4 px-6 font-mono text-xs text-slate-400">
                        {plan.id.split("-")[0]}
                      </td>
                      <td className="py-4 px-6 font-semibold text-slate-800">
                        {plan.patient?.name || "Desconocido"}
                      </td>
                      <td className="py-4 px-6 text-slate-600 font-mono">
                        {plan.tdee_calculated} kcal
                      </td>
                      <td className="py-4 px-6 text-slate-500 text-xs">
                        {formattedDate}
                      </td>
                      <td className="py-4 px-6">
                        <span
                          className={`inline-block px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider border ${plan.status === "PLAN APROBADO" ? "bg-green-50 text-green-700 border-green-200" : "bg-blue-50 text-blue-700 border-blue-200"}`}
                        >
                          {plan.status}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
