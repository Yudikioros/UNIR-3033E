import React from "react";

export default function ConfigPage() {
  return (
    <div className="flex-1 flex flex-col h-full bg-[#F8FAFC] overflow-hidden">
      {/* Topbar */}
      <header className="bg-white border-b border-slate-200 px-8 py-5 flex justify-between items-center flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Configuración</h1>
          <p className="text-xs text-slate-500 mt-1">
            Perfil profesional, parámetros de cálculo y base de conocimiento
          </p>
        </div>
      </header>

      {/* Contenido scrolleable con estilo limpio */}
      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <main className="max-w-5xl mx-auto space-y-6">
          {/* SECTION 1: NUTRITIONIST PROFILE */}
          <section className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-semibold text-slate-800 text-sm">
                Perfil del nutriólogo
              </h2>
            </div>
            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              <InputField
                label="Nombre"
                defaultValue="Nutriólogo responsable"
              />
              <InputField label="Cédula profesional" defaultValue="00000000" />
            </div>
          </section>

          {/* SECTION 2: CALCULATION METHODS & PARAMETERS */}
          <section className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-semibold text-slate-800 text-sm">
                Métodos de cálculo y parámetros
              </h2>
            </div>
            <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
              <SelectField
                label="Método energético predeterminado"
                options={["Mifflin - St Jeor", "Harris-Benedict", "FAO/OMS"]}
              />
              <SelectField
                label="Tolerancia energética del plan"
                options={["± 10 %", "± 5 %", "± 15 %"]}
              />
              <InputField label="Proteína (g/kg peso)" defaultValue="1.8" />
              <InputField
                label="Grasa (% del total energético)"
                defaultValue="30 %"
              />
            </div>
          </section>

          {/* SECTION 3: KNOWLEDGE BASE */}
          <section className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-semibold text-slate-800 text-sm">
                Base de conocimiento
              </h2>
            </div>
            <div className="p-6 grid grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-slate-400 mb-1">Versión</p>
                <p className="font-medium text-slate-800 text-sm">KB-1.0</p>
              </div>
              <div>
                <p className="text-xs text-slate-400 mb-1">
                  Documentos indexados
                </p>
                <p className="font-medium text-slate-800 text-sm">5</p>
              </div>
              <div>
                <p className="text-xs text-slate-400 mb-1">
                  Última actualización
                </p>
                <p className="font-medium text-slate-800 text-sm">
                  12 ago 2026
                </p>
              </div>
            </div>
          </section>

          {/* SECTION 4: SYSTEM PREFERENCES */}
          <section className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-semibold text-slate-800 text-sm">
                Preferencias del sistema
              </h2>
            </div>
            <div className="p-6 flex flex-col divide-y divide-slate-100">
              <ToggleRow
                title="Mostrar siempre las fuentes en el plan"
                description="Cada recomendación indica el documento del que proviene"
                defaultChecked
              />
              <ToggleRow
                title="Requerir confirmación explícita al aprobar"
                description="Casilla obligatoria antes de registrar el plan"
                defaultChecked
              />
              <ToggleRow
                title="Permitir exportar borradores sin aprobar"
                description="Desactivado por seguridad clínica"
                defaultChecked={false}
              />
              <ToggleRow
                title="Registrar trazabilidad de cada generación"
                description="ID, modelo, base de conocimiento y fuentes recuperadas"
                defaultChecked
              />
            </div>

            {/* INFO FOOTER */}
            <div className="bg-slate-50 px-6 py-4 border-t border-slate-100">
              <p className="text-xs text-slate-500">
                Los módulos clínicos especializados (pediatría, renal, diabetes,
                hipertensión) permanecen desactivados en esta versión del MVP.
              </p>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

// --- HELPER COMPONENTS ---

function InputField({
  label,
  defaultValue,
}: {
  label: string;
  defaultValue: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-semibold text-slate-600">{label}</label>
      <input
        type="text"
        defaultValue={defaultValue}
        className="w-full border border-slate-300 rounded-lg py-2 px-3 text-sm focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all bg-slate-50/50 text-slate-800"
      />
    </div>
  );
}

function SelectField({ label, options }: { label: string; options: string[] }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-semibold text-slate-600">{label}</label>
      <select className="w-full border border-slate-300 rounded-lg py-2 px-3 text-sm focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all bg-slate-50/50 text-slate-800">
        {options.map((optionLabel, index) => (
          <option key={index}>{optionLabel}</option>
        ))}
      </select>
    </div>
  );
}

function ToggleRow({
  title,
  description,
  defaultChecked,
}: {
  title: string;
  description: string;
  defaultChecked: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-4 first:pt-0 last:pb-0">
      <div>
        <p className="text-sm font-semibold text-slate-800">{title}</p>
        <p className="text-xs text-slate-500 mt-0.5">{description}</p>
      </div>
      <label className="relative inline-flex items-center cursor-pointer flex-shrink-0">
        <input
          type="checkbox"
          className="sr-only peer"
          defaultChecked={defaultChecked}
        />
        <div className="w-11 h-6 bg-slate-200 rounded-full peer peer-checked:bg-green-500 peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
      </label>
    </div>
  );
}
