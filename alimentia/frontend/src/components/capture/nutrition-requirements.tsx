"use client";
import { useState } from "react";
import {
  calculateConsultation,
  errorMessage,
  updateConsultation,
} from "../../services/api";
import type { Consultation } from "../../services/types";
import { primaryButton, secondaryButton, Notice } from "./fields";

const METHOD_LABELS: Record<string, string> = {
  MIFFLIN_ST_JEOR: "Mifflin-St Jeor",
};

function metric(value: number | null, decimals: number, suffix = ""): string {
  return value === null ? "—" : `${value.toFixed(decimals)}${suffix}`;
}

export function NutritionRequirements({
  consultation,
  onCalculated,
}: {
  consultation?: Consultation;
  onCalculated: (consultation: Consultation) => void;
}) {
  const [calculating, setCalculating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [overrides, setOverrides] = useState<Record<string, string>>({});

  function loadOverrides(current: Consultation) {
    setOverrides({
      targetCaloriesOverride: current.targetCaloriesOverride?.toString() ?? "",
      proteinGramsOverride: current.proteinGramsOverride?.toString() ?? "",
      carbohydrateGramsOverride:
        current.carbohydrateGramsOverride?.toString() ?? "",
      fatGramsOverride: current.fatGramsOverride?.toString() ?? "",
      fiberGramsOverride: current.fiberGramsOverride?.toString() ?? "",
      waterLitersOverride: current.waterLitersOverride?.toString() ?? "",
    });
  }

  function numberOrNull(value: string): number | null {
    return value.trim() ? Number(value) : null;
  }

  async function calculate() {
    if (!consultation || calculating) return;
    setCalculating(true);
    setError("");
    try {
      onCalculated(await calculateConsultation(consultation.id));
    } catch (err) {
      setError(
        errorMessage(err, "No fue posible calcular los requerimientos."),
      );
    } finally {
      setCalculating(false);
    }
  }

  async function saveOverrides() {
    if (!consultation || saving || !consultation.isEditable) return;
    setSaving(true);
    setError("");
    try {
      const saved = await updateConsultation(consultation.id, {
        targetCaloriesOverride: numberOrNull(overrides.targetCaloriesOverride),
        proteinGramsOverride: numberOrNull(overrides.proteinGramsOverride),
        carbohydrateGramsOverride: numberOrNull(
          overrides.carbohydrateGramsOverride,
        ),
        fatGramsOverride: numberOrNull(overrides.fatGramsOverride),
        fiberGramsOverride: numberOrNull(overrides.fiberGramsOverride),
        waterLitersOverride: numberOrNull(overrides.waterLitersOverride),
        expectedUpdatedAt: consultation.updatedAt,
      });
      onCalculated(await calculateConsultation(saved.id));
      setEditing(false);
    } catch (err) {
      setError(
        errorMessage(err, "No fue posible guardar los valores personalizados."),
      );
    } finally {
      setSaving(false);
    }
  }

  if (!consultation) {
    return (
      <p className="py-8 text-center text-sm text-slate-400">
        Abre una consulta para calcular sus requerimientos.
      </p>
    );
  }

  const calculated = consultation.targetCalories !== null;
  const blocked = consultation.readinessIssues.length > 0;
  const methodLabel = consultation.calculationMethod
    ? (METHOD_LABELS[consultation.calculationMethod] ??
      consultation.calculationMethod)
    : null;

  return (
    <div className="space-y-4">
      {error ? <Notice error>{error}</Notice> : null}
      {calculated ? (
        <>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs font-semibold text-slate-500">IMC</dt>
              <dd className="font-semibold text-slate-800">
                {metric(consultation.bmi, 1)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-slate-500">
                Metabolismo basal
              </dt>
              <dd className="font-semibold text-slate-800">
                {metric(consultation.basalMetabolicRate, 0, " kcal")}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-slate-500">
                Gasto energético total
              </dt>
              <dd className="font-semibold text-slate-800">
                {metric(consultation.totalEnergyExpenditure, 0, " kcal")}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-slate-500">
                Energía objetivo
              </dt>
              <dd className="font-semibold text-blue-700">
                {metric(consultation.targetCalories, 0, " kcal")}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-slate-500">Proteína</dt>
              <dd className="font-semibold text-slate-800">
                {metric(consultation.proteinGrams, 1, " g")}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-slate-500">
                Carbohidratos
              </dt>
              <dd className="font-semibold text-slate-800">
                {metric(consultation.carbohydrateGrams, 1, " g")}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-slate-500">Grasas</dt>
              <dd className="font-semibold text-slate-800">
                {metric(consultation.fatGrams, 1, " g")}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-slate-500">Fibra</dt>
              <dd className="font-semibold text-slate-800">
                {metric(consultation.fiberGrams, 1, " g")}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-slate-500">Agua</dt>
              <dd className="font-semibold text-slate-800">
                {metric(consultation.waterLiters, 2, " L")}
              </dd>
            </div>
          </dl>
          <p className="text-xs text-slate-400">
            Calculado mediante reglas
            {methodLabel ? ` · Método: ${methodLabel}` : ""}
            {consultation.calculationRuleVersion
              ? ` (v${consultation.calculationRuleVersion})`
              : ""}
            . No proviene de IA generativa.
          </p>
          <button
            className={secondaryButton}
            onClick={calculate}
            disabled={calculating || blocked}
          >
            {calculating ? "Recalculando…" : "Recalcular requerimientos"}
          </button>
          {consultation.isEditable ? (
            <>
              <button
                className={secondaryButton}
                onClick={() => {
                  loadOverrides(consultation);
                  setEditing(!editing);
                }}
                disabled={saving}
              >
                {editing ? "Cerrar edición" : "Editar valores"}
              </button>
              {editing ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <p className="mb-3 text-xs text-slate-500">
                    Los valores informados sustituyen solo las reglas
                    automáticas de esta consulta. Deja un campo vacío para
                    restaurar su cálculo.
                  </p>
                  <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
                    {[
                      [
                        "targetCaloriesOverride",
                        "Energía objetivo (kcal)",
                        "any",
                      ],
                      ["proteinGramsOverride", "Proteína (g)", "any"],
                      ["carbohydrateGramsOverride", "Carbohidratos (g)", "any"],
                      ["fatGramsOverride", "Grasas (g)", "any"],
                      ["fiberGramsOverride", "Fibra (g)", "any"],
                      ["waterLitersOverride", "Agua (L)", "any"],
                    ].map(([name, label, step]) => (
                      <label
                        key={name}
                        className="font-semibold text-slate-600"
                      >
                        {label}
                        <input
                          className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm font-medium text-slate-900"
                          type="number"
                          step={step}
                          min="0"
                          value={overrides[name] ?? ""}
                          onChange={(event) =>
                            setOverrides({
                              ...overrides,
                              [name]: event.target.value,
                            })
                          }
                        />
                      </label>
                    ))}
                  </div>
                  <button
                    className={`${primaryButton} mt-4`}
                    onClick={saveOverrides}
                    disabled={saving}
                  >
                    {saving ? "Guardando…" : "Guardar y recalcular"}
                  </button>
                </div>
              ) : null}
            </>
          ) : null}
        </>
      ) : (
        <>
          <p className="text-sm text-slate-500">
            Cálculo pendiente para esta consulta.
          </p>
          <button
            className={primaryButton}
            onClick={calculate}
            disabled={calculating || blocked}
          >
            {calculating ? "Calculando…" : "Calcular requerimientos"}
          </button>
        </>
      )}
      {blocked ? (
        <ul className="list-disc space-y-1 pl-5 text-xs text-slate-500">
          {consultation.readinessIssues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
