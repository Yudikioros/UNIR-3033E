"use client";

import React from "react";
import { CheckCircle, AlertTriangle, Info } from "lucide-react";

// --- TYPES & MOCK DATA ---

type AlertSeverity = "success" | "warning" | "info";

interface AlertData {
  id: string;
  severity: AlertSeverity;
  title: string;
  category: string;
  context: string;
  timestamp: string;
}

const ALERTS_DATA: AlertData[] = [
  {
    id: "1",
    severity: "success",
    title: "Plan dentro del rango energético objetivo (± 10 %).",
    category: "REGLA",
    context: "María González ALG-000045-03",
    timestamp: "Hoy, 11:42",
  },
  {
    id: "2",
    severity: "warning",
    title: "Fibra por debajo del objetivo establecido para el plan.",
    category: "VALIDACIÓN",
    context: "María González ALG-000045-03",
    timestamp: "Hoy, 11:42",
  },
  {
    id: "3",
    severity: "success",
    title: "Distribución de macronutrientes dentro de parámetros definidos.",
    category: "REGLA",
    context: "Lucía Ramírez ALG-000043-01",
    timestamp: "Ayer, 17:05",
  },
  {
    id: "4",
    severity: "warning",
    title: "Revisar preferencia alimentaria registrada: el paciente indicó no consumir mariscos.",
    category: "FUENTE",
    context: "Jorge Alcántara ALG-000044-02",
    timestamp: "Ayer, 09:30",
  },
  {
    id: "5",
    severity: "info",
    title: "Presupuesto diario estimado por encima del rango capturado.",
    category: "REGLA",
    context: "Diego Márquez ALG-000041-04",
    timestamp: "21 ago, 16:12",
  },
  {
    id: "6",
    severity: "success",
    title: "Equivalentes SMAE verificados contra la base de conocimiento.",
    category: "VALIDACIÓN",
    context: "Ana Beltrán ALG-000042-02",
    timestamp: "22 ago, 12:58",
  },
];

// --- MAIN COMPONENT ---

export default function AlertsPage() {
  return (
    <div className="flex-1 flex flex-col h-full bg-[#F8FAFC] overflow-hidden">
      {/* Topbar */}
      <header className="bg-white border-b border-slate-200 px-8 py-5 flex justify-between items-center flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Alertas</h1>
          <p className="text-xs text-slate-500 mt-1">
            Historial de validaciones generadas por el motor de reglas. No constituyen diagnóstico ni indicación clínica.
          </p>
        </div>
      </header>

      {/* Contenido scrolleable */}
      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <div className="max-w-6xl mx-auto">
          
          {/* ALERTS LIST CONTAINER */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="flex flex-col divide-y divide-slate-100">
              {ALERTS_DATA.map((alert) => (
                <AlertRow key={alert.id} data={alert} />
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

// --- HELPER COMPONENTS ---

function AlertRow({ data }: { data: AlertData }) {
  const renderIcon = () => {
    switch (data.severity) {
      case "success":
        return (
          <CheckCircle
            size={18}
            className="text-green-500 mt-0.5 flex-shrink-0"
          />
        );
      case "warning":
        return (
          <AlertTriangle
            size={18}
            className="text-orange-400 mt-0.5 flex-shrink-0"
          />
        );
      case "info":
        return (
          <Info size={18} className="text-blue-500 mt-0.5 flex-shrink-0" />
        );
      default:
        return null;
    }
  };

  return (
    <div className="p-5 flex items-start justify-between hover:bg-slate-50/50 transition-colors group">
      <div className="flex gap-4">
        {renderIcon()}

        <div className="flex flex-col gap-1.5">
          <p className="text-sm font-medium text-slate-800 leading-tight">
            {data.title}
          </p>
          <div className="flex items-center gap-2">
            <span className="bg-slate-100 text-slate-600 text-[10px] font-bold px-2 py-0.5 rounded tracking-wide font-mono">
              {data.category}
            </span>
            <span className="text-xs text-slate-400 font-medium">{data.context}</span>
          </div>
        </div>
      </div>

      <div className="text-xs text-slate-400 flex-shrink-0 whitespace-nowrap mt-1">
        {data.timestamp}
      </div>
    </div>
  );
}