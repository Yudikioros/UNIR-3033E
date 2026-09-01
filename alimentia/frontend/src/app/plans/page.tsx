import React from "react";

const PLANES_DATA = [
  {
    id: "ALG-000045-03",
    patient: "María González",
    goal: "Pérdida de peso",
    energy: "1,850 kcal",
    date: "25 ago 2026",
    status: "EN REVISIÓN",
  },
  {
    id: "ALG-000044-02",
    patient: "Jorge Alcántara",
    goal: "Mantenimiento",
    energy: "2,400 kcal",
    date: "24 ago 2026",
    status: "PLAN APROBADO",
  },
  {
    id: "ALG-000043-01",
    patient: "Lucía Ramírez",
    goal: "Incremento de peso",
    energy: "2,100 kcal",
    date: "24 ago 2026",
    status: "BORRADOR",
  },
];

export default function PlanesPage() {
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
                <th className="py-3.5 px-6">Energía</th>
                <th className="py-3.5 px-6">Fecha</th>
                <th className="py-3.5 px-6">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
              {PLANES_DATA.map((plan, i) => (
                <tr
                  key={i}
                  className="hover:bg-slate-50/50 transition-colors cursor-pointer"
                >
                  <td className="py-4 px-6 font-mono text-xs text-slate-400">
                    {plan.id}
                  </td>
                  <td className="py-4 px-6 font-semibold text-slate-800">
                    {plan.patient}
                  </td>
                  <td className="py-4 px-6 text-slate-600">{plan.energy}</td>
                  <td className="py-4 px-6 text-slate-500 text-xs">
                    {plan.date}
                  </td>
                  <td className="py-4 px-6">
                    <span
                      className={`inline-block px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider border ${plan.status === "PLAN APROBADO" ? "bg-green-50 text-green-700 border-green-200" : plan.status === "EN REVISIÓN" ? "bg-orange-50 text-orange-700 border-orange-200" : "bg-blue-50 text-blue-700 border-blue-200"}`}
                    >
                      {plan.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
