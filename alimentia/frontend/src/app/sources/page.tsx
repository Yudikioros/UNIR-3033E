import React from "react";
import { BookOpen } from "lucide-react";

// --- TYPES & MOCK DATA ---

interface SourceItem {
  id: string;
  title: string;
  institution: string;
  version: string;
  date: string;
  status: "Vigente" | "Actualizado";
}

const SOURCES_DATA: SourceItem[] = [
  {
    id: "1",
    title: "Sistema Mexicano de Alimentos Equivalentes (SMAE)",
    institution: "Fomento de Nutrición y Salud A.C.",
    version: "4.ª ed.",
    date: "2014",
    status: "Vigente",
  },
  {
    id: "2",
    title: "Tablas de composición de alimentos",
    institution: "Instituto Nacional de Salud Pública (INSP)",
    version: "ed. 2015",
    date: "2015",
    status: "Vigente",
  },
  {
    id: "3",
    title: "NOM-043-SSA2-2012, Servicios básicos de salud",
    institution: "Secretaría de Salud (México)",
    version: "DOF 22-01-2013",
    date: "2013",
    status: "Vigente",
  },
  {
    id: "4",
    title: "Guía de práctica para el manejo dietético del adulto sano",
    institution: "Base documental AlimentIA",
    version: "KB-1.0",
    date: "12 ago 2026",
    status: "Vigente",
  },
  {
    id: "5",
    title: "Recomendaciones de ingesta de fibra dietética",
    institution: "Academy of Nutrition and Dietetics",
    version: "2021",
    date: "2021",
    status: "Vigente",
  },
];

// --- MAIN COMPONENT ---

export default function SourcesPage() {
  return (
    <div className="flex-1 flex flex-col h-full bg-[#F8FAFC] overflow-hidden">
      {/* Topbar */}
      <header className="bg-white border-b border-slate-200 px-8 py-5 flex justify-between items-center flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Fuentes</h1>
          <p className="text-xs text-slate-500 mt-1">
            Biblioteca autorizada que alimenta la base de conocimiento (RAG). El
            modelo de lenguaje sólo puede citar documentos de esta lista.
          </p>
        </div>
      </header>

      {/* Contenido scrolleable */}
      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <div className="max-w-7xl mx-auto">
          {/* SOURCES TABLE CONTAINER */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/50 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="py-3.5 px-6">Fuente</th>
                  <th className="py-3.5 px-6">Institución</th>
                  <th className="py-3.5 px-6">Versión</th>
                  <th className="py-3.5 px-6">Fecha</th>
                  <th className="py-3.5 px-6">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
                {SOURCES_DATA.map((source) => (
                  <SourceRow key={source.id} data={source} />
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

function SourceRow({ data }: { data: SourceItem }) {
  return (
    <tr className="hover:bg-slate-50/50 transition-colors">
      <td className="py-4 px-6 font-medium text-slate-800 flex items-center gap-3">
        <div className="bg-blue-50 p-2 rounded-xl text-blue-600 flex-shrink-0">
          <BookOpen size={16} />
        </div>
        <span>{data.title}</span>
      </td>
      <td className="py-4 px-6 text-slate-600 text-sm">{data.institution}</td>
      <td className="py-4 px-6 text-slate-600 font-mono text-xs">
        {data.version}
      </td>
      <td className="py-4 px-6 text-slate-500 text-xs">{data.date}</td>
      <td className="py-4 px-6">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider bg-green-50 text-green-700 border border-green-200">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
          {data.status}
        </span>
      </td>
    </tr>
  );
}
