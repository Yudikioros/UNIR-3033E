"use client";
import { useRef, useState } from "react";
import { createConsultation, updateConsultation, errorMessage } from "../../services/api";
import type { CaptureOptions, Consultation, ConsultationCreate, Patient } from "../../services/types";
import { Fields, dietaryFields, habitFields, dietaryText, dietaryJson, numberValue, textValue, optionValue, primaryButton, secondaryButton, Notice } from "./fields";

function initialValues(patient: Patient, consultation?: Consultation): Record<string, string> {
  const date = new Date();
  const today = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  return {
    consultationDate: consultation?.consultationDate.slice(0, 10) ?? today,
    ageAtConsultation: (consultation ? consultation.ageAtConsultation : patient.currentAge)?.toString() ?? "",
    sex: (consultation ? consultation.sex : patient.sex) ?? "",
    weightKg: consultation?.weightKg?.toString() ?? "", heightM: consultation?.heightM?.toString() ?? "",
    activityLevel: (consultation ? consultation.activityLevel : patient.defaultActivityLevel) ?? "",
    goal: (consultation ? consultation.goal : patient.defaultGoal) ?? "",
    mealsPerDay: (consultation ? consultation.mealsPerDay : patient.defaultMealsPerDay)?.toString() ?? "",
    dailyBudget: (consultation ? consultation.dailyBudget : patient.defaultDailyBudget)?.toString() ?? "",
    budgetMin: consultation?.budgetMin?.toString() ?? "", budgetMax: consultation?.budgetMax?.toString() ?? "",
    foodPreferences: dietaryText(consultation ? consultation.foodPreferences : patient.foodPreferences),
    foodsToAvoid: dietaryText(consultation ? consultation.foodsToAvoid : patient.foodsToAvoid),
    allergiesOrIntolerances: dietaryText(consultation ? consultation.allergiesOrIntolerances : patient.allergiesOrIntolerances),
    notes: consultation?.notes ?? "",
  };
}

export function ConsultationForm({ patient, consultation, options, onSaved, onDirtyChange }: {
  patient: Patient; consultation?: Consultation; options: CaptureOptions;
  onSaved: (consultation: Consultation) => void; onDirtyChange: (dirty: boolean) => void;
}) {
  const [initial] = useState(() => initialValues(patient, consultation));
  const [values, setValues] = useState(initial);
  const [review, setReview] = useState(consultation?.requiresProfessionalReview ?? false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const submitting = useRef(false);
  const request = useRef<{ body: string; key: string } | null>(null);
  const editable = consultation?.isEditable ?? true;
  const dirty = JSON.stringify(values) !== JSON.stringify(initial) || review !== (consultation?.requiresProfessionalReview ?? false);

  function change(name: string, value: string) {
    const next = { ...values, [name]: value };
    setValues(next);
    onDirtyChange(JSON.stringify(next) !== JSON.stringify(initial) || review !== (consultation?.requiresProfessionalReview ?? false));
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current || !editable) return;
    const button = (event.nativeEvent as SubmitEvent).submitter;
    const status = button instanceof HTMLButtonElement && button.value === "READY" ? "READY" : "DRAFT";
    const payload: ConsultationCreate = {
      consultationDate: values.consultationDate ? `${values.consultationDate}T00:00:00Z` : null,
      ageAtConsultation: numberValue(values.ageAtConsultation), sex: optionValue(values.sex, options.sex),
      weightKg: numberValue(values.weightKg), heightM: numberValue(values.heightM),
      activityLevel: optionValue(values.activityLevel, options.activity), goal: optionValue(values.goal, options.goal),
      mealsPerDay: numberValue(values.mealsPerDay), dailyBudget: numberValue(values.dailyBudget),
      budgetMin: numberValue(values.budgetMin), budgetMax: numberValue(values.budgetMax),
      foodPreferences: dietaryJson(values.foodPreferences), foodsToAvoid: dietaryJson(values.foodsToAvoid),
      allergiesOrIntolerances: dietaryJson(values.allergiesOrIntolerances), notes: textValue(values.notes),
      requiresProfessionalReview: review, status,
    };
    submitting.current = true; setSaving(true); setError("");
    try {
      let saved: Consultation;
      if (consultation) saved = await updateConsultation(consultation.id, { ...payload, expectedUpdatedAt: consultation.updatedAt });
      else {
        const body = JSON.stringify(payload);
        if (request.current?.body !== body) request.current = { body, key: crypto.randomUUID() };
        saved = await createConsultation(patient.id, payload, request.current.key);
      }
      onDirtyChange(false); onSaved(saved);
    } catch (err) { setError(errorMessage(err, "No fue posible guardar la consulta.")); }
    finally { submitting.current = false; setSaving(false); }
  }

  return <form onSubmit={submit} className="space-y-5">
    <p className="text-xs text-slate-500">Estos datos describen al paciente en esta consulta y se conservan en su historial.</p>
    {error ? <Notice error>{error}</Notice> : null}
    {!editable ? <Notice>{consultation?.status === "READY" ? "Consulta lista para la siguiente fase. Sus datos están protegidos." : "Consulta histórica con resultados o planes asociados. Sus datos están protegidos."} Para registrar cambios, crea una nueva consulta.</Notice> : null}
    {patient.conditions.length || review ? <Notice>{consultation?.scopeWarning || options.scopeWarning}</Notice> : null}
    <fieldset disabled={saving || !editable} className="space-y-5">
      <Fields values={values} limits={options.consultationLimits} onChange={change} fields={[
        { name: "consultationDate", label: "Fecha de consulta", type: "date", required: true },
        { name: "ageAtConsultation", label: "Edad en esta consulta", type: "number", step: "1" },
        { name: "sex", label: "Sexo registrado en consulta", type: "select", options: options.sex },
        { name: "weightKg", label: "Peso (kg)", type: "number", step: "any" },
        { name: "heightM", label: "Talla (m)", type: "number", step: "any" },
      ]} />
      <Fields values={values} limits={options.consultationLimits} onChange={change} fields={habitFields(options, false)} />
      <p className="text-xs text-slate-500">Si indicas un rango de presupuesto, deja vacío el presupuesto diario.</p>
      <Fields values={values} limits={options.consultationLimits} onChange={change} fields={[
        { name: "budgetMin", label: "Presupuesto mínimo (MXN)", type: "number", step: "any" },
        { name: "budgetMax", label: "Presupuesto máximo (MXN)", type: "number", step: "any" },
      ]} />
      <Fields values={values} limits={options.consultationLimits} onChange={change} fields={dietaryFields()} />
      <label className="flex items-start gap-2 text-xs text-slate-600"><input type="checkbox" checked={review} onChange={event => {
        setReview(event.target.checked); onDirtyChange(JSON.stringify(values) !== JSON.stringify(initial) || event.target.checked !== (consultation?.requiresProfessionalReview ?? false));
      }} />Se declaró una condición que puede requerir revisión profesional fuera del alcance del MVP.</label>
    </fieldset>
    {editable && consultation?.readinessIssues.length && !dirty ? <ul className="list-disc space-y-1 pl-5 text-xs text-slate-500">{consultation.readinessIssues.map(issue => <li key={issue}>{issue}</li>)}</ul> : null}
    <div className="flex flex-wrap gap-3">
      <button type="submit" value="DRAFT" disabled={saving || !editable || (!!consultation && !dirty)} className={primaryButton}>{saving ? (consultation ? "Guardando…" : "Creando consulta…") : "Guardar consulta"}</button>
      <button type="submit" value="READY" disabled={saving || !editable} className={secondaryButton}>Marcar lista</button>
    </div>
    <p className="text-xs text-slate-400">Marcar lista valida los datos y finaliza la captura.</p>
  </form>;
}
