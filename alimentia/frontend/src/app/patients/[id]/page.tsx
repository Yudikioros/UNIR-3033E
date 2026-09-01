"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { generateDietDraft, PatientData } from "../../../services/api";

// --- MOCK DATABASE ---
const MOCK_DB: Record<string, any> = {
  "1": { name: "María González", age: 28, gender: "Femenino", weight: 68, height: 1.65, goal: "Pérdida de peso", pathologies: "Resistencia a la insulina", allergies: "Mariscos, Lactosa", preferences: "Alta en vegetales" },
  "2": { name: "Jorge Alcántara", age: 41, gender: "Masculino", weight: 82, height: 1.78, goal: "Mantenimiento", pathologies: "Ninguna", allergies: "Ninguna", preferences: "Sin restricciones" },
  "3": { name: "Lucía Ramírez", age: 34, gender: "Femenino", weight: 55, height: 1.60, goal: "Incremento de peso", pathologies: "Ninguna", allergies: "Gluten", preferences: "Avena, Pollo" },
};

export default function PatientPlanPage() {
  const params = useParams();
  const patientId = params.id as string;
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  const [formData, setFormData] = useState({
    name: "Cargando...",
    age: 0,
    gender: "Femenino",
    weight: 0,
    height: 0,
    goal: "",
    activity_level: "Moderada",
    method: "Mifflin - St Jeor",
    pathologies: "",
    allergies: "",
    preferences: "",
    meals_count: "5 comidas al día",
    budget: "$120 - $160 MXN",
    observations: "",
  });

  // Cargar datos simulados de la BD al montar el componente
  useEffect(() => {
    if (MOCK_DB[patientId]) {
      setFormData((prev) => ({ ...prev, ...MOCK_DB[patientId] }));
    } else {
      setFormData((prev) => ({ ...prev, name: "Paciente Nuevo" }));
    }
  }, [patientId]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    const payload: PatientData = {
      age: Number(formData.age),
      gender: formData.gender === "Masculino" ? "male" : "female",
      weight: Number(formData.weight),
      height: Number(formData.height),
      goal: formData.goal,
      activity_level: "light",
      pathologies: formData.pathologies.split(",").map((s) => s.trim()).filter((s) => s.toLowerCase() !== "ninguna"),
      allergies_intolerances: formData.allergies.split(",").map((s) => s.trim()).filter((s) => s.toLowerCase() !== "ninguna"),
      food_preferences: formData.preferences.split(",").map((s) => s.trim()).filter((s) => s.toLowerCase() !== "sin restricciones"),
      medications: [],
      cultural_restrictions: [],
      budget: formData.budget,
      regional_availability: "México",
    };

    try {
      const data = await generateDietDraft(payload);
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Error al conectar con el servidor.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F8FAFC] overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-8 py-4 flex justify-between items-center flex-shrink-0">
        <div className="flex items-center gap-4">
          <Link href="/pacientes" className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7"></path></svg>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-slate-800">Paciente: {formData.name}</h1>
            <p className="text-xs text-slate-500">Adultos sin patologías clínicas complejas — alcance del MVP</p>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start pb-8">
          
          {/* ================= FORMULARIO (Igual al anterior pero dinámico) ================= */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <h3 className="text-sm font-bold text-blue-600 mb-6 flex items-center gap-2 uppercase tracking-wide">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
              1. Datos del paciente
            </h3>
            
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="grid grid-cols-2 gap-5">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5">Edad</label>
                  <input type="number" name="age" value={formData.age} onChange={handleInputChange} className="w-full bg-slate-50/50 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5">Sexo</label>
                  <select name="gender" value={formData.gender} onChange={handleInputChange} className="w-full bg-slate-50/50 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500">
                    <option>Femenino</option>
                    <option>Masculino</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-5">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5">Peso (kg)</label>
                  <input type="number" step="0.1" name="weight" value={formData.weight} onChange={handleInputChange} className="w-full bg-slate-50/50 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5">Talla (m)</label>
                  <input type="number" step="0.01" name="height" value={formData.height} onChange={handleInputChange} className="w-full bg-slate-50/50 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-5">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5">Objetivo</label>
                  <select name="goal" value={formData.goal} onChange={handleInputChange} className="w-full bg-slate-50/50 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500">
                    <option value="Pérdida de peso">Pérdida de peso</option>
                    <option value="Mantenimiento">Mantenimiento</option>
                    <option value="Incremento de peso">Incremento de peso</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5">Nivel de actividad</label>
                  <select name="activity_level" value={formData.activity_level} onChange={handleInputChange} className="w-full bg-slate-50/50 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500">
                    <option>Ligera</option>
                    <option>Moderada</option>
                    <option>Intensa</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-5 pt-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5">Preferencias alimentarias</label>
                  <input type="text" name="preferences" value={formData.preferences} onChange={handleInputChange} className="w-full bg-slate-50/50 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5">Alimentos que no consume</label>
                  <input type="text" name="allergies" value={formData.allergies} onChange={handleInputChange} className="w-full bg-slate-50/50 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Patologías</label>
                <input type="text" name="pathologies" value={formData.pathologies} onChange={handleInputChange} className="w-full bg-slate-50/50 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500" />
              </div>

              <button 
                type="submit" 
                disabled={loading}
                className={`w-full mt-4 py-3 rounded-lg font-bold text-white flex items-center justify-center gap-2 transition-all shadow-md ${loading ? 'bg-slate-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'}`}
              >
                {loading ? 'Calculando...' : 'Recalcular y generar borrador'}
              </button>
            </form>
          </div>

          {/* ================= RESULTADOS (Simplificado para el ejemplo) ================= */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col min-h-[600px]">
            <h3 className="text-sm font-bold text-blue-600 mb-6 uppercase tracking-wide">2. Plan dietético generado</h3>
            
            {!result && !loading ? (
              <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">Haz clic en generar para ver el plan de {formData.name}.</div>
            ) : loading ? (
               <div className="flex-1 flex items-center justify-center text-blue-600">Generando...</div>
            ) : (
              <div className="flex-1 overflow-y-auto custom-scrollbar pr-2">
                 <div className="bg-slate-50 p-4 rounded-lg text-center mb-4 border border-slate-100">
                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Energía Objetivo</p>
                    <p className="font-bold text-2xl text-slate-800">{result.calculated_requirements?.tdee_kcal} <span className="text-xs text-slate-400 font-normal">kcal/día</span></p>
                 </div>
                 
                 {result.diet_plan?.meals?.map((meal: any, idx: number) => (
                    <div key={idx} className="mb-4 bg-slate-50 p-3 rounded-lg border border-slate-100">
                      <h4 className="font-bold text-sm text-slate-700">{meal.time}</h4>
                      <ul className="mt-2 space-y-1">
                        {meal.items.map((item: any, i: number) => (
                          <li key={i} className="text-xs text-slate-600 flex justify-between">
                            <span>{item.food} ({item.quantity})</span>
                            <span className="font-mono text-slate-400">{item.calories} kcal</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}