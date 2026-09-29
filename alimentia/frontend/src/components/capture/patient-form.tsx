"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { ApiError, createPatient, updatePatient, errorMessage } from "../../services/api";
import type { CaptureOptions, Patient, PatientCreate } from "../../services/types";
import { Fields, dietaryFields, habitFields, dietaryText, dietaryJson, numberValue, textValue, optionValue, primaryButton, Notice } from "./fields";

function initialValues(patient?: Patient): Record<string, string> {
  return {
    name: patient?.name ?? "", sex: patient?.sex ?? "", birthDate: patient?.birthDate?.slice(0, 10) ?? "",
    age: patient?.age?.toString() ?? "", email: patient?.email ?? "", phone: patient?.phone ?? "",
    defaultActivityLevel: patient?.defaultActivityLevel ?? "", defaultGoal: patient?.defaultGoal ?? "",
    defaultMealsPerDay: patient?.defaultMealsPerDay?.toString() ?? "", defaultDailyBudget: patient?.defaultDailyBudget?.toString() ?? "",
    foodPreferences: dietaryText(patient?.foodPreferences), foodsToAvoid: dietaryText(patient?.foodsToAvoid),
    allergiesOrIntolerances: dietaryText(patient?.allergiesOrIntolerances), notes: patient?.notes ?? "",
  };
}

export function PatientForm({ patient, options, onSaved, onDirtyChange }: {
  patient?: Patient; options: CaptureOptions; onSaved: (patient: Patient) => void; onDirtyChange?: (dirty: boolean) => void;
}) {
  const [initial] = useState(() => initialValues(patient));
  const [values, setValues] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [existingId, setExistingId] = useState<string>();
  const submitting = useRef(false);
  const request = useRef<{ body: string; key: string } | null>(null);
  const dirty = JSON.stringify(values) !== JSON.stringify(initial);

  function change(name: string, value: string) {
    const next = { ...values, [name]: value };
    if (name === "birthDate" && value) next.age = "";
    if (name === "age" && value) next.birthDate = "";
    setValues(next);
    onDirtyChange?.(JSON.stringify(next) !== JSON.stringify(initial));
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    const sex = optionValue(values.sex, options.sex);
    if (!sex) { setError("Selecciona el sexo del paciente."); return; }
    const payload: PatientCreate = {
      name: values.name.trim(), sex, birthDate: values.birthDate ? `${values.birthDate}T00:00:00Z` : null,
      age: numberValue(values.age), email: textValue(values.email), phone: textValue(values.phone),
      defaultActivityLevel: optionValue(values.defaultActivityLevel, options.activity), defaultGoal: optionValue(values.defaultGoal, options.goal),
      defaultMealsPerDay: numberValue(values.defaultMealsPerDay), defaultDailyBudget: numberValue(values.defaultDailyBudget),
      foodPreferences: dietaryJson(values.foodPreferences), foodsToAvoid: dietaryJson(values.foodsToAvoid),
      allergiesOrIntolerances: dietaryJson(values.allergiesOrIntolerances), notes: textValue(values.notes),
    };
    submitting.current = true;
    setSaving(true); setError(""); setExistingId(undefined);
    try {
      let saved: Patient;
      if (patient) {
        const changed = Object.fromEntries(Object.entries(payload).filter(([key]) => values[key] !== initial[key]));
        saved = await updatePatient(patient.id, { ...changed, expectedUpdatedAt: patient.updatedAt });
      } else {
        const body = JSON.stringify(payload);
        if (request.current?.body !== body) request.current = { body, key: crypto.randomUUID() };
        saved = await createPatient(payload, request.current.key);
      }
      onDirtyChange?.(false);
      onSaved(saved);
    } catch (err) {
      setError(errorMessage(err, "No fue posible guardar los cambios."));
      if (err instanceof ApiError) setExistingId(err.existingId);
    } finally { submitting.current = false; setSaving(false); }
  }

  return <form onSubmit={submit} className="space-y-5">
    {error ? <Notice error>{error}{existingId ? <Link className="ml-2 underline" href={`/patients/${existingId}`}>Abrir ficha existente</Link> : null}</Notice> : null}
    <fieldset disabled={saving} className="space-y-5">
      <Fields values={values} limits={options.patientLimits} onChange={change} fields={[
        { name: "name", label: "Nombre", required: true, wide: true },
        { name: "birthDate", label: "Fecha de nacimiento", type: "date" },
        { name: "age", label: "Edad registrada (si no conoce la fecha)", type: "number", step: "1", disabled: !!values.birthDate },
        { name: "sex", label: "Sexo", type: "select", options: options.sex, required: true },
        { name: "email", label: "Correo electrónico", type: "email" },
        { name: "phone", label: "Teléfono" },
      ]} />
      <details><summary className="cursor-pointer text-xs font-semibold text-blue-600">Datos habituales y preferencias (opcionales)</summary>
        <div className="mt-5 space-y-5"><Fields values={values} limits={options.patientLimits} onChange={change} fields={habitFields(options, true)} />
          <Fields values={values} limits={options.patientLimits} onChange={change} fields={dietaryFields()} /></div>
      </details>
    </fieldset>
    <button type="submit" disabled={saving || (!!patient && !dirty)} className={primaryButton}>{saving ? "Guardando…" : patient ? "Guardar paciente" : "Crear paciente"}</button>
    {patient?.conditions.length ? <p className="text-xs text-amber-800">Antecedentes históricos conservados: {patient.conditions.join("; ")}. Requieren revisión profesional.</p> : null}
  </form>;
}
