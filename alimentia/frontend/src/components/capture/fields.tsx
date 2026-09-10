import type { CaptureOptions, FieldLimits, Option } from "../../services/types";

export const primaryButton = "inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50";
export const secondaryButton = "inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const control = "mt-1.5 w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:bg-slate-100 disabled:text-slate-500";

export interface FieldSpec {
  name: string;
  label: string;
  type?: "text" | "number" | "date" | "email" | "textarea" | "select";
  options?: Option[];
  required?: boolean;
  disabled?: boolean;
  wide?: boolean;
  step?: string;
}

export function Fields({ fields, values, limits, onChange }: {
  fields: FieldSpec[]; values: Record<string, string>; limits: Record<string, FieldLimits>;
  onChange: (name: string, value: string) => void;
}) {
  return <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">{fields.map(field => {
    const limit = limits[field.name] || {};
    const props = { name: field.name, value: values[field.name] ?? "", required: field.required,
      disabled: field.disabled, className: control, onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => onChange(field.name, event.target.value) };
    return <label key={field.name} className={`block text-xs font-semibold text-slate-600 ${field.wide ? "sm:col-span-2" : ""}`}>
      {field.label}{field.required ? " *" : ""}
      {field.type === "textarea" ? <textarea {...props} rows={3} maxLength={limit.maxLength} /> : field.type === "select" ?
        <select {...props}><option value="">Sin especificar</option>
          {values[field.name] && !field.options?.some(option => option.value === values[field.name]) ? <option value={values[field.name]}>{values[field.name]} (histórico)</option> : null}
          {field.options?.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select> : <input {...props} type={field.type || "text"} step={field.step}
          min={limit.minimum ?? limit.exclusiveMinimum} max={limit.maximum} minLength={limit.minLength} maxLength={limit.maxLength} />}
    </label>;
  })}</div>;
}

export function dietaryFields(): FieldSpec[] {
  return [
    { name: "foodPreferences", label: "Preferencias alimentarias (una por línea)", type: "textarea" },
    { name: "foodsToAvoid", label: "Alimentos que evita (uno por línea)", type: "textarea" },
    { name: "allergiesOrIntolerances", label: "Alergias/intolerancias simples (una por línea)", type: "textarea" },
    { name: "notes", label: "Observaciones", type: "textarea" },
  ];
}

export function habitFields(options: CaptureOptions, patient: boolean): FieldSpec[] {
  return [
    { name: patient ? "defaultActivityLevel" : "activityLevel", label: patient ? "Actividad habitual" : "Actividad actual", type: "select", options: options.activity },
    { name: patient ? "defaultGoal" : "goal", label: patient ? "Objetivo habitual" : "Objetivo actual", type: "select", options: options.goal },
    { name: patient ? "defaultMealsPerDay" : "mealsPerDay", label: "Número de comidas", type: "number", step: "1" },
    { name: patient ? "defaultDailyBudget" : "dailyBudget", label: "Presupuesto diario (MXN)", type: "number", step: "any" },
  ];
}

export function dietaryText(raw?: string | null): string {
  if (!raw) return "";
  try {
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.every((item): item is string => typeof item === "string")) return parsed.join("\n");
  } catch { /* Historical free text remains visible. */ }
  return raw;
}
export const dietaryJson = (text: string) => JSON.stringify([...new Set(text.split("\n").map(item => item.trim()).filter(Boolean))]);
export const numberValue = (value: string) => value.trim() ? Number(value) : null;
export const textValue = (value: string) => value.trim() || null;
export function optionValue<T extends string>(value: string, options: Option<T>[]): T | null {
  return options.find(option => option.value === value)?.value ?? null;
}
export function dateLabel(value?: string | null) {
  return value ? new Date(value).toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" }) : "—";
}
export function optionLabel(value: string | null | undefined, options: Option[]) {
  return options.find(option => option.value === value)?.label ?? value ?? "—";
}
export function Notice({ children, error = false }: { children: React.ReactNode; error?: boolean }) {
  return <div role={error ? "alert" : "status"} className={`rounded-lg border p-3 text-sm ${error ? "border-red-200 bg-red-50 text-red-700" : "border-blue-100 bg-blue-50 text-blue-800"}`}>{children}</div>;
}
