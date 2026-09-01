export default function ResumenPage() {
  return (
    <div className="flex-1 flex flex-col h-full bg-[#F8FAFC] overflow-hidden">
      {/* Topbar */}
      <header className="bg-white border-b border-slate-200 px-8 py-5 flex justify-between items-center flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Resumen</h1>
          <p className="text-xs text-slate-500 mt-1">
            Actividad de tu consulta — 25 de agosto de 2026
          </p>
        </div>
      </header>

      {/* Contenido scrolleable con fondo claro y ancho completo */}
      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <div className="w-full space-y-6">
          {/* ================= TARJETAS DE MÉTRICAS ================= */}
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
              <div className="flex items-center gap-2 text-blue-600 mb-2">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
                  ></path>
                </svg>
                <h3 className="text-xs font-semibold text-slate-600">
                  Pacientes activos
                </h3>
              </div>
              <p className="text-3xl font-bold text-slate-800">24</p>
              <p className="text-[10px] font-medium text-green-600 mt-1">
                +3 esta semana
              </p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
              <div className="flex items-center gap-2 text-blue-600 mb-2">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                  ></path>
                </svg>
                <h3 className="text-xs font-semibold text-slate-600">
                  Planes generados
                </h3>
              </div>
              <p className="text-3xl font-bold text-slate-800">68</p>
              <p className="text-[10px] text-slate-400 mt-1">Últimos 30 días</p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-orange-200 shadow-sm bg-orange-50/30">
              <div className="flex items-center gap-2 text-orange-500 mb-2">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                  ></path>
                </svg>
                <h3 className="text-xs font-semibold text-slate-600">
                  Pendientes de revisión
                </h3>
              </div>
              <p className="text-3xl font-bold text-slate-800">5</p>
              <p className="text-[10px] text-orange-600 font-medium mt-1">
                Requieren tu atención
              </p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
              <div className="flex items-center gap-2 text-green-500 mb-2">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M5 13l4 4L19 7"
                  ></path>
                </svg>
                <h3 className="text-xs font-semibold text-slate-600">
                  Planes aprobados
                </h3>
              </div>
              <p className="text-3xl font-bold text-slate-800">57</p>
              <p className="text-[10px] text-slate-400 mt-1">84% del total</p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
              <div className="flex items-center gap-2 text-slate-400 mb-2">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                  ></path>
                </svg>
                <h3 className="text-xs font-semibold text-slate-600">
                  Tiempo promedio
                </h3>
              </div>
              <p className="text-3xl font-bold text-slate-800">6.4</p>
              <p className="text-[10px] text-slate-400 mt-1">
                minutos por plan
              </p>
            </div>
          </div>

          {/* ================= SECCIÓN INFERIOR ================= */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Tabla de Pacientes */}
            <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-5 border-b border-slate-100 flex justify-between items-center">
                <h3 className="font-bold text-slate-700">
                  Pacientes recientes
                </h3>
                <span className="text-xs text-blue-600 font-semibold cursor-pointer hover:underline">
                  Ver todos
                </span>
              </div>
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 border-b border-slate-100">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Paciente</th>
                    <th className="px-5 py-3 font-semibold">Edad</th>
                    <th className="px-5 py-3 font-semibold">Objetivo</th>
                    <th className="px-5 py-3 font-semibold">Últ. consulta</th>
                    <th className="px-5 py-3 font-semibold">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-5 py-4 font-semibold text-slate-800">
                      María González
                    </td>
                    <td className="px-5 py-4 text-slate-600">28</td>
                    <td className="px-5 py-4 text-slate-600">
                      Pérdida de peso
                    </td>
                    <td className="px-5 py-4 text-slate-500 text-xs">
                      25 ago 2026
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-[10px] font-bold bg-orange-100 text-orange-700 px-2 py-1 rounded border border-orange-200">
                        EN REVISIÓN
                      </span>
                    </td>
                  </tr>
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-5 py-4 font-semibold text-slate-800">
                      Jorge Alcántara
                    </td>
                    <td className="px-5 py-4 text-slate-600">41</td>
                    <td className="px-5 py-4 text-slate-600">Mantenimiento</td>
                    <td className="px-5 py-4 text-slate-500 text-xs">
                      24 ago 2026
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-[10px] font-bold bg-green-100 text-green-700 px-2 py-1 rounded border border-green-200">
                        PLAN APROBADO
                      </span>
                    </td>
                  </tr>
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-5 py-4 font-semibold text-slate-800">
                      Lucía Ramírez
                    </td>
                    <td className="px-5 py-4 text-slate-600">34</td>
                    <td className="px-5 py-4 text-slate-600">
                      Incremento de peso
                    </td>
                    <td className="px-5 py-4 text-slate-500 text-xs">
                      24 ago 2026
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-[10px] font-bold bg-blue-100 text-blue-700 px-2 py-1 rounded border border-blue-200">
                        BORRADOR
                      </span>
                    </td>
                  </tr>
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-5 py-4 font-semibold text-slate-800">
                      Ana Beltrán
                    </td>
                    <td className="px-5 py-4 text-slate-600">52</td>
                    <td className="px-5 py-4 text-slate-600">
                      Pérdida de peso
                    </td>
                    <td className="px-5 py-4 text-slate-500 text-xs">
                      22 ago 2026
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-[10px] font-bold bg-green-100 text-green-700 px-2 py-1 rounded border border-green-200">
                        PLAN APROBADO
                      </span>
                    </td>
                  </tr>
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-5 py-4 font-semibold text-slate-800">
                      Diego Márquez
                    </td>
                    <td className="px-5 py-4 text-slate-600">26</td>
                    <td className="px-5 py-4 text-slate-600">
                      Incremento de peso
                    </td>
                    <td className="px-5 py-4 text-slate-500 text-xs">
                      21 ago 2026
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-[10px] font-bold bg-yellow-100 text-yellow-700 px-2 py-1 rounded border border-yellow-200">
                        MODIFICADO
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Panel lateral derecho */}
            <div className="space-y-6">
              <div className="bg-white rounded-2xl border border-orange-200 shadow-sm overflow-hidden">
                <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-orange-50/30">
                  <h3 className="font-bold text-orange-800 text-sm flex items-center gap-2">
                    Pendientes de revisión
                  </h3>
                  <span className="bg-orange-200 text-orange-800 text-[10px] font-bold px-2 py-0.5 rounded-full">
                    5
                  </span>
                </div>
                <div className="divide-y divide-slate-100">
                  {[
                    {
                      name: "María González",
                      id: "ALG-000045-03",
                      time: "hace 12 min",
                    },
                    {
                      name: "Lucía Ramírez",
                      id: "ALG-000043-01",
                      time: "hace 1 h",
                    },
                    {
                      name: "Jorge Alcántara",
                      id: "ALG-000044-02",
                      time: "ayer",
                    },
                    {
                      name: "Diego Márquez",
                      id: "ALG-000041-04",
                      time: "ayer",
                    },
                    {
                      name: "Ana Beltrán",
                      id: "ALG-000042-02",
                      time: "hace 3 d",
                    },
                  ].map((item, idx) => (
                    <div
                      key={idx}
                      className="p-4 hover:bg-slate-50 cursor-pointer flex justify-between items-center transition-colors"
                    >
                      <div>
                        <p className="text-sm font-semibold text-slate-700">
                          {item.name}
                        </p>
                        <p className="text-[10px] font-mono text-slate-400 mt-0.5">
                          {item.id}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400">
                          {item.time}
                        </span>
                        <svg
                          className="w-4 h-4 text-slate-300"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M9 5l7 7-7 7"
                          ></path>
                        </svg>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-blue-50/50 rounded-2xl border border-blue-100 p-5">
                <h4 className="text-xs font-bold text-blue-800 mb-2 uppercase tracking-wide">
                  Principio del sistema
                </h4>
                <p className="text-xs text-blue-700/80 leading-relaxed">
                  AlimentIA prepara y propone. El nutriólogo revisa y decide.
                  Ningún plan se considera válido sin aprobación explícita del
                  profesional responsable.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
