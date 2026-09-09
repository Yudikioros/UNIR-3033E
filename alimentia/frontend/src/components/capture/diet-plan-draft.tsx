"use client";
import { useEffect, useRef, useState } from "react";
import { startGenerateDraft, startRegeneratePlan, getGenerationStatus, getConsultationPlans, editPlan, approvePlan, rejectPlan, downloadPlanPdf, getPlanTraceability, errorMessage } from "../../services/api";
import type { Consultation, DietPlanDetail, DietPlanMealEdit, GenerationStatus, PlanTraceability, ValidationSeverity } from "../../services/types";
import { primaryButton, secondaryButton, dateLabel, Notice } from "./fields";
import { GenerationProgress } from "./generation-progress";

// Polling real del progreso (sección 4 de la corrección de UX): sin SSE,
// sin WebSockets, sin temporizadores que fabriquen etapas — cada iteración
// consulta GET /generations/{id}/status y refleja exactamente lo que
// devuelve el backend.
const POLL_INTERVAL_MS = 1500;
const generationSessionKey = (consultationId: string) => `alimentia:generation:${consultationId}`;

async function pollGenerationStatus(generationId: string, isCancelled: () => boolean,
                                     onUpdate: (status: GenerationStatus) => void): Promise<GenerationStatus | null> {
  while (!isCancelled()) {
    const status = await getGenerationStatus(generationId);
    if (isCancelled()) return null;
    onUpdate(status);
    if (status.status !== "IN_PROGRESS") return status;
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
  }
  return null;
}

const SEVERITY_STYLE: Record<ValidationSeverity, string> = {
  ERROR: "border-red-200 bg-red-50 text-red-700",
  WARNING: "border-amber-200 bg-amber-50 text-amber-800",
  INFO: "border-blue-100 bg-blue-50 text-blue-800",
};
const SEVERITY_HINT: Record<ValidationSeverity, string> = {
  ERROR: " Debe corregirse antes de aprobar.",
  WARNING: " Requiere revisión profesional.",
  INFO: "",
};
const dangerButton = "inline-flex items-center justify-center rounded-lg border border-red-200 px-3 py-2 text-xs font-semibold text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50";
const dangerSolidButton = "inline-flex items-center justify-center rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50";
const inputClass = "w-full rounded-md border border-slate-300 px-2 py-1 text-xs";

function toEditMeals(plan: DietPlanDetail): DietPlanMealEdit[] {
  return plan.meals.map(meal => ({
    mealType: meal.mealType, name: meal.name,
    foods: meal.foods.map(food => ({
      foodName: food.foodName, quantity: food.quantity ?? 1, unit: food.unit ?? "",
      smaeEquivalent: food.smaeEquivalent, calories: food.calories, protein: food.protein,
      carbohydrates: food.carbohydrates, fat: food.fat, notes: food.notes,
    })),
  }));
}

export function DietPlanDraft({ consultation, initialPlanId, onGenerated }: {
  consultation?: Consultation; initialPlanId?: string; onGenerated?: (planId: string) => void;
}) {
  const [versions, setVersions] = useState<DietPlanDetail[]>();
  const [selected, setSelected] = useState<number>();
  const [loadError, setLoadError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [job, setJob] = useState<GenerationStatus>();
  const [actionError, setActionError] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const [regenJob, setRegenJob] = useState<GenerationStatus>();
  // Vida del componente (nunca se reinicia salvo al desmontar): usada por
  // generate()/doRegenerate(), que arrancan por una acción del usuario, no
  // por un cambio de props.
  const unmountedRef = useRef(false);
  useEffect(() => {
    unmountedRef.current = false;
    return () => { unmountedRef.current = true; };
  }, []);

  const [editing, setEditing] = useState(false);
  const [editMeals, setEditMeals] = useState<DietPlanMealEdit[]>([]);

  const [showRegenerate, setShowRegenerate] = useState(false);
  const [instructions, setInstructions] = useState("");
  const [showReject, setShowReject] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [showApproveConfirm, setShowApproveConfirm] = useState(false);

  useEffect(() => {
    if (!consultation) return;
    const controller = new AbortController();
    // Bandera propia de ESTA ejecución del efecto (no del componente): si
    // `consultation.id` cambia sin desmontar (p. ej. navegar entre planes
    // reutilizando la misma instancia), esta ejecución debe cancelarse sin
    // afectar la bandera de una ejecución nueva.
    let cancelled = false;
    getConsultationPlans(consultation.id, controller.signal)
      .then(list => {
        setVersions(list);
        const requestedIndex = initialPlanId ? list.findIndex(plan => plan.id === initialPlanId) : -1;
        setSelected(list.length ? (requestedIndex >= 0 ? requestedIndex : list.length - 1) : undefined);
      })
      .catch(err => { if (!controller.signal.aborted) setLoadError(errorMessage(err, "No fue posible cargar el plan.")); });

    // Recuperación tras recarga (sección 14): si había una generación en
    // curso para esta consulta, se retoma el polling real del progreso real
    // en vez de perderla y dejar al usuario sin retroalimentación.
    const storedId = sessionStorage.getItem(generationSessionKey(consultation.id));
    if (storedId) {
      getGenerationStatus(storedId).then(async status => {
        if (controller.signal.aborted) return;
        setGenerating(true);
        if (status.status !== "IN_PROGRESS") {
          sessionStorage.removeItem(generationSessionKey(consultation.id));
          setGenerating(false);
          if (status.status === "SUCCESS") {
            const list = await getConsultationPlans(consultation.id);
            setVersions(list);
            setSelected(list.length - 1);
          }
          return;
        }
        setJob(status);
        const final = await pollGenerationStatus(storedId, () => cancelled, setJob);
        if (!final) return;
        sessionStorage.removeItem(generationSessionKey(consultation.id));
        setGenerating(false);
        if (final.status === "SUCCESS") {
          const list = await getConsultationPlans(consultation.id);
          setVersions(list);
          setSelected(list.length - 1);
        }
      }).catch(() => { sessionStorage.removeItem(generationSessionKey(consultation.id)); setGenerating(false); });
    }

    return () => { controller.abort(); cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [consultation?.id]);

  const calculated = consultation?.targetCalories != null;
  const blockedToGenerate = !consultation || !calculated || consultation.readinessIssues.length > 0;
  const current = versions && selected !== undefined ? versions[selected] : undefined;

  async function refresh() {
    if (!consultation) return;
    const list = await getConsultationPlans(consultation.id);
    setVersions(list);
    setSelected(list.length - 1);
  }

  async function generate() {
    if (!consultation || generating) return;
    setGenerating(true); setActionError(""); setJob(undefined);
    try {
      const { generationId } = await startGenerateDraft(consultation.id);
      sessionStorage.setItem(generationSessionKey(consultation.id), generationId);
      const final = await pollGenerationStatus(generationId, () => unmountedRef.current, setJob);
      if (!final) return;
      sessionStorage.removeItem(generationSessionKey(consultation.id));
      if (final.status === "SUCCESS") {
        await refresh();
        if (final.dietPlanId) onGenerated?.(final.dietPlanId);
      }
    } catch (err) {
      if (unmountedRef.current) return;
      setActionError(errorMessage(err, "No fue posible generar el borrador. El proveedor puede tardar varios minutos o no estar disponible; intenta nuevamente."));
      setJob(undefined);
    } finally {
      if (!unmountedRef.current) setGenerating(false);
    }
  }

  function retryGenerate() {
    setJob(undefined);
    generate();
  }

  function startEdit() {
    if (!current) return;
    setEditMeals(toEditMeals(current));
    setEditing(true);
    setActionError("");
  }

  function updateFood(mi: number, fi: number, patch: Partial<DietPlanMealEdit["foods"][number]>) {
    setEditMeals(meals => meals.map((meal, i) => i !== mi ? meal : {
      ...meal, foods: meal.foods.map((food, j) => j !== fi ? food : { ...food, ...patch }),
    }));
  }
  function removeFood(mi: number, fi: number) {
    setEditMeals(meals => meals.map((meal, i) => i !== mi ? meal : { ...meal, foods: meal.foods.filter((_, j) => j !== fi) }));
  }
  function addFood(mi: number) {
    setEditMeals(meals => meals.map((meal, i) => i !== mi ? meal : { ...meal, foods: [...meal.foods, { foodName: "", quantity: 1, unit: "g" }] }));
  }
  function updateMeal(mi: number, patch: Partial<DietPlanMealEdit>) {
    setEditMeals(meals => meals.map((meal, i) => i !== mi ? meal : { ...meal, ...patch }));
  }
  function removeMeal(mi: number) {
    setEditMeals(meals => meals.filter((_, i) => i !== mi));
  }
  function addMeal() {
    setEditMeals(meals => [...meals, { mealType: "Comida", name: "Nueva comida", foods: [{ foodName: "", quantity: 1, unit: "g" }] }]);
  }

  async function saveEdit() {
    if (!current || actionBusy) return;
    const cleaned = editMeals
      .map(meal => ({ ...meal, foods: meal.foods.filter(food => food.foodName.trim()) }))
      .filter(meal => meal.foods.length > 0);
    if (!cleaned.length) { setActionError("El plan debe tener al menos una comida con un alimento."); return; }
    setActionBusy(true); setActionError("");
    try {
      await editPlan(current.id, { meals: cleaned, expectedUpdatedAt: current.updatedAt });
      setEditing(false);
      await refresh();
    } catch (err) {
      setActionError(errorMessage(err, "No fue posible guardar los cambios."));
    } finally {
      setActionBusy(false);
    }
  }

  async function doApprove() {
    if (!current || actionBusy) return;
    setActionBusy(true); setActionError("");
    try {
      await approvePlan(current.id);
      setShowApproveConfirm(false);
      await refresh();
    } catch (err) {
      setActionError(errorMessage(err, "No fue posible aprobar el plan."));
      setShowApproveConfirm(false);
    } finally {
      setActionBusy(false);
    }
  }

  async function doReject() {
    if (!current || actionBusy || !rejectReason.trim()) return;
    setActionBusy(true); setActionError("");
    try {
      await rejectPlan(current.id, rejectReason.trim());
      setShowReject(false); setRejectReason("");
      await refresh();
    } catch (err) {
      setActionError(errorMessage(err, "No fue posible rechazar el plan."));
    } finally {
      setActionBusy(false);
    }
  }

  async function doRegenerate() {
    if (!current || actionBusy) return;
    setActionBusy(true); setActionError(""); setRegenJob(undefined);
    try {
      const { generationId } = await startRegeneratePlan(current.id, instructions.trim() || undefined);
      setShowRegenerate(false); setInstructions("");
      sessionStorage.setItem(generationSessionKey(current.consultationId), generationId);
      const final = await pollGenerationStatus(generationId, () => unmountedRef.current, setRegenJob);
      if (!final) return;
      sessionStorage.removeItem(generationSessionKey(current.consultationId));
      if (final.status === "SUCCESS") await refresh();
    } catch (err) {
      if (unmountedRef.current) return;
      setActionError(errorMessage(err, "No fue posible generar una nueva versión. Intenta nuevamente."));
      setRegenJob(undefined);
    } finally {
      if (!unmountedRef.current) setActionBusy(false);
    }
  }

  function retryRegenerate() {
    setRegenJob(undefined);
    doRegenerate();
  }

  if (!consultation) {
    return <p className="py-8 text-center text-sm text-slate-400">Abre una consulta para generar un borrador.</p>;
  }
  if (loadError) return <Notice error>{loadError}</Notice>;
  if (versions === undefined) return <p role="status" className="py-8 text-center text-sm text-slate-400">Cargando plan…</p>;

  return <div className="space-y-4">
    {actionError ? <Notice error>{actionError}</Notice> : null}
    {!calculated ? <p className="text-xs text-slate-500">Calcula los requerimientos nutricionales antes de generar el borrador.</p> : null}

    {!versions.length ? (
      <div className="space-y-3">
        {!job ? (
          <button className={primaryButton} onClick={generate} disabled={generating || blockedToGenerate}>
            {generating ? "Generando borrador…" : "Generar borrador"}
          </button>
        ) : null}
        {generating && !job ? <Notice>Iniciando generación…</Notice> : null}
        {job ? <GenerationProgress status={job.status} stage={job.stage} startedAt={job.startedAt}
          error={job.errorMessage} onRetry={retryGenerate} /> : null}
      </div>
    ) : current ? <>
      {versions.length > 1 ? <div className="flex flex-wrap gap-2">
        {versions.map((version, index) => (
          <button key={version.id} onClick={() => setSelected(index)}
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${index === selected ? "border-blue-500 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-500 hover:bg-slate-50"}`}>
            Versión {version.version}
          </button>
        ))}
      </div> : null}

      <StatusBanner plan={current} />
      <PlanSummaryPanel plan={current} />

      {editing ? (
        <EditForm meals={editMeals} onUpdateMeal={updateMeal} onRemoveMeal={removeMeal} onAddMeal={addMeal}
          onUpdateFood={updateFood} onRemoveFood={removeFood} onAddFood={addFood}
          onSave={saveEdit} onCancel={() => setEditing(false)} busy={actionBusy} />
      ) : <>
        {current.summary ? <div className="rounded-lg border border-slate-200 bg-white p-3">
          <p className="text-xs font-semibold text-slate-600">Resumen</p>
          <p className="mt-1 text-xs text-slate-600">{current.summary}</p>
        </div> : null}

        <div className="space-y-3">
          <p className="text-xs font-semibold text-slate-600">Comidas</p>
          {current.meals.map(meal => <div key={meal.id} className="rounded-lg border border-slate-200 p-3">
            <p className="text-sm font-semibold text-slate-700">{meal.name} <span className="font-normal text-slate-400">({meal.mealType})</span></p>
            <ul className="mt-2 space-y-1 text-xs text-slate-600">
              {meal.foods.map(food => <li key={food.id}>
                <span>
                  {food.foodName} — {food.quantity ?? "—"} {food.unit ?? ""}
                  {food.calories != null ? ` · ${food.calories} kcal` : ""}
                  {food.smaeEquivalent ? ` · SMAE: ${food.smaeEquivalent}` : ""}
                </span>
                {food.notes ? <span className="block text-slate-400 italic">{food.notes}</span> : null}
              </li>)}
            </ul>
          </div>)}
        </div>

        {current.recommendations.length ? <div className="space-y-1">
          <p className="text-xs font-semibold text-slate-600">Recomendaciones</p>
          <ul className="list-disc space-y-1 pl-5 text-xs text-slate-600">
            {current.recommendations.map((recommendation, index) => <li key={index}>{recommendation}</li>)}
          </ul>
        </div> : null}

        <ValidationsList validations={current.validations} />
        <SourcesBlock plan={current} />

        {regenJob ? <GenerationProgress status={regenJob.status} stage={regenJob.stage} startedAt={regenJob.startedAt}
          error={regenJob.errorMessage} onRetry={retryRegenerate} /> : null}

        {current.isEditable ? <div className="flex flex-wrap gap-3 border-t border-slate-100 pt-4">
          <button className={secondaryButton} onClick={startEdit} disabled={actionBusy}>Editar plan</button>
          <button className={secondaryButton} onClick={() => setShowRegenerate(true)} disabled={actionBusy}>Regenerar</button>
          <button className={primaryButton} onClick={() => setShowApproveConfirm(true)} disabled={actionBusy}>
            Aprobar plan{current.blockingValidationCount ? ` (${current.blockingValidationCount} pendiente${current.blockingValidationCount > 1 ? "s" : ""})` : ""}
          </button>
          <button className={dangerButton} onClick={() => setShowReject(true)} disabled={actionBusy}>Rechazar</button>
        </div> : current.status === "REJECTED" ? <div className="border-t border-slate-100 pt-4">
          <button className={secondaryButton} onClick={() => setShowRegenerate(true)} disabled={actionBusy}>Regenerar</button>
        </div> : null}

        <ExportAndTraceability plan={current} />

        {showApproveConfirm ? <ConfirmApprove onConfirm={doApprove} onCancel={() => setShowApproveConfirm(false)} busy={actionBusy} /> : null}
        {showReject ? <RejectForm reason={rejectReason} onChange={setRejectReason} onConfirm={doReject} onCancel={() => setShowReject(false)} busy={actionBusy} /> : null}
        {showRegenerate ? <RegenerateForm instructions={instructions} onChange={setInstructions} onConfirm={doRegenerate} onCancel={() => setShowRegenerate(false)} busy={actionBusy} /> : null}
      </>}
    </> : null}
  </div>;
}

function StatusBanner({ plan }: { plan: DietPlanDetail }) {
  if (plan.status === "APPROVED") {
    return <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3">
      <p className="text-xs font-bold uppercase tracking-wide text-green-700">APROBADO · versión {plan.version}</p>
      <p className="text-xs text-green-700">
        Revisado y aprobado por profesional{plan.approvedBy ? ` (${plan.approvedBy})` : ""}
        {plan.approvedAt ? ` · ${new Date(plan.approvedAt).toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" })}` : ""}
      </p>
    </div>;
  }
  if (plan.status === "REJECTED") {
    return <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
      <p className="text-xs font-bold uppercase tracking-wide text-red-700">RECHAZADO · versión {plan.version}</p>
      <p className="text-xs text-red-700">
        {plan.rejectionReason}
        {plan.rejectedAt ? ` · ${new Date(plan.rejectedAt).toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" })}` : ""}
      </p>
    </div>;
  }
  const label = plan.status === "UNDER_REVIEW" ? "EN REVISIÓN" : "BORRADOR";
  return <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
    <p className="text-xs font-bold uppercase tracking-wide text-amber-700">{label} · versión {plan.version}</p>
    <p className="text-xs text-amber-700">Pendiente de revisión profesional</p>
  </div>;
}

function PlanSummaryPanel({ plan }: { plan: DietPlanDetail }) {
  const deviation = plan.totalCalories != null && plan.targetCalories
    ? (plan.totalCalories - plan.targetCalories) / plan.targetCalories * 100 : null;
  const cell = (label: string, value: string) => <div>
    <p className="text-[10px] uppercase tracking-wide text-slate-400">{label}</p>
    <p className="text-xs font-semibold text-slate-700">{value}</p>
  </div>;
  return <div className="grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-4">
    {cell("Fecha de generación", plan.generatedAt ? dateLabel(plan.generatedAt) : "—")}
    {cell("Energía objetivo", plan.targetCalories != null ? `${Math.round(plan.targetCalories)} kcal` : "—")}
    {cell("Energía del plan", plan.totalCalories != null ? `${Math.round(plan.totalCalories)} kcal` : "—")}
    <div>
      <p className="text-[10px] uppercase tracking-wide text-slate-400">Desviación</p>
      <p className={`text-xs font-semibold ${deviation == null ? "text-slate-700" : Math.abs(deviation) <= 5 ? "text-green-600" : "text-red-600"}`}>
        {deviation != null ? `${deviation > 0 ? "+" : ""}${deviation.toFixed(1)}%` : "—"}
      </p>
    </div>
    {cell("Proteína", plan.proteinGrams != null ? `${plan.proteinGrams} g${plan.targetProteinGrams != null ? ` / ${Math.round(plan.targetProteinGrams)} g obj.` : ""}` : "—")}
    {cell("Carbohidratos", plan.carbohydrateGrams != null ? `${plan.carbohydrateGrams} g${plan.targetCarbohydrateGrams != null ? ` / ${Math.round(plan.targetCarbohydrateGrams)} g obj.` : ""}` : "—")}
    {cell("Grasa", plan.fatGrams != null ? `${plan.fatGrams} g${plan.targetFatGrams != null ? ` / ${Math.round(plan.targetFatGrams)} g obj.` : ""}` : "—")}
    {cell("Fibra / Agua", `${plan.fiberGrams != null ? `${plan.fiberGrams} g` : "—"} / ${plan.waterLiters != null ? `${plan.waterLiters} L` : "—"}`)}
  </div>;
}

function ValidationsList({ validations }: { validations: DietPlanDetail["validations"] }) {
  if (!validations.length) return null;
  const blocking = validations.filter(validation => validation.isBlocking);
  const warnings = validations.filter(validation => !validation.isBlocking && validation.severity === "WARNING");
  const info = validations.filter(validation => !validation.isBlocking && validation.severity !== "WARNING");
  return <div className="space-y-2">
    <p className="text-xs font-semibold text-slate-600">Validaciones</p>
    {blocking.length ? <Notice error>Este plan no puede aprobarse hasta corregir las validaciones bloqueantes.</Notice> : null}
    <ValidationGroup title="Bloqueantes" items={blocking} />
    <ValidationGroup title="Advertencias" items={warnings} />
    <ValidationGroup title="Informativas" items={info} />
  </div>;
}

function ValidationGroup({ title, items }: { title: string; items: DietPlanDetail["validations"] }) {
  if (!items.length) return null;
  return <div className="space-y-1">
    <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{title}</p>
    {items.map(validation => <div key={validation.id} className={`rounded-lg border px-3 py-2 text-xs ${SEVERITY_STYLE[validation.severity]}`}>
      <span className="font-bold">{validation.severity}: </span>{validation.message}{SEVERITY_HINT[validation.severity]}
    </div>)}
  </div>;
}

function SourcesBlock({ plan }: { plan: DietPlanDetail }) {
  const knowledgeUnavailable = plan.validations.some(v => v.code === "KNOWLEDGE_BASE_UNAVAILABLE");
  const foodUnavailable = plan.validations.some(v => v.code === "FOOD_DATABASE_UNAVAILABLE");
  return <div className="space-y-1">
    <p className="text-xs font-semibold text-slate-600">Fuentes utilizadas</p>
    {plan.sources.length ? <ul className="list-disc space-y-1 pl-5 text-xs text-slate-600">
      {plan.sources.map(source => <li key={source.id}>{source.documentName}{source.institution ? ` — ${source.institution}` : ""}</li>)}
    </ul> : <p className="text-xs text-slate-500">Ninguna fuente documental configurada.</p>}
    {knowledgeUnavailable ? <p className="text-xs text-amber-700">
      La base de conocimiento documental aún no está configurada. El borrador fue generado sin contexto RAG.
    </p> : null}
    {foodUnavailable ? <p className="text-xs text-amber-700">La base alimentaria estructurada aún no está configurada.</p> : null}
  </div>;
}

function ExportAndTraceability({ plan }: { plan: DietPlanDetail }) {
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [showTrace, setShowTrace] = useState(false);
  const [trace, setTrace] = useState<PlanTraceability>();
  const [traceError, setTraceError] = useState("");

  async function onExport() {
    if (exporting) return;
    setExporting(true); setExportError("");
    try {
      await downloadPlanPdf(plan.id);
    } catch (err) {
      setExportError(errorMessage(err, "No fue posible exportar el plan a PDF."));
    } finally {
      setExporting(false);
    }
  }

  async function onToggleTrace() {
    if (showTrace) { setShowTrace(false); return; }
    setShowTrace(true);
    if (trace) return;
    try {
      setTrace(await getPlanTraceability(plan.id));
    } catch (err) {
      setTraceError(errorMessage(err, "No fue posible cargar la trazabilidad."));
    }
  }

  return <div className="space-y-3 border-t border-slate-100 pt-4">
    <div className="flex flex-wrap items-center gap-3">
      {plan.status === "APPROVED" ? (
        <button className={secondaryButton} onClick={onExport} disabled={exporting}>
          {exporting ? "Exportando…" : "Exportar PDF"}
        </button>
      ) : null}
      <button className="text-xs font-semibold text-slate-500 underline decoration-dotted hover:text-slate-700" onClick={onToggleTrace}>
        {showTrace ? "Ocultar trazabilidad técnica" : "Ver trazabilidad técnica"}
      </button>
    </div>
    {exportError ? <Notice error>{exportError}</Notice> : null}
    {showTrace ? (
      traceError ? <Notice error>{traceError}</Notice> :
      !trace ? <p className="text-xs text-slate-400">Cargando trazabilidad…</p> :
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 space-y-1">
        <p><span className="font-semibold">Cálculo:</span> {trace.calculation.method ?? "—"} (ruleset {trace.calculation.rulesetVersion ?? "—"})</p>
        <p><span className="font-semibold">Generación:</span> {trace.generation.modelProvider ?? "—"}/{trace.generation.modelName ?? "—"} · prompt {trace.generation.promptVersion ?? "—"} · KB {trace.generation.knowledgeBaseVersion ?? "—"}</p>
        <p><span className="font-semibold">Recursos:</span> BAM {trace.resources.foodDatabaseUsed ? `usado (${trace.resources.foodDatabaseName} ${trace.resources.foodDatabaseVersion})` : "no usado"} · RAG {trace.resources.knowledgeBaseUsed ? "usado" : "no usado"}</p>
        <p><span className="font-semibold">Intervención humana:</span> {trace.humanReview.manualEditCount} edición(es) · {trace.humanReview.regenerationCount} regeneración(es) solicitada(s)</p>
        {trace.sources.length ? <p><span className="font-semibold">Fuentes:</span> {trace.sources.map(s => s.name).join(", ")}</p> : null}
      </div>
    ) : null}
  </div>;
}

function EditForm({ meals, onUpdateMeal, onRemoveMeal, onAddMeal, onUpdateFood, onRemoveFood, onAddFood, onSave, onCancel, busy }: {
  meals: DietPlanMealEdit[];
  onUpdateMeal: (index: number, patch: Partial<DietPlanMealEdit>) => void;
  onRemoveMeal: (index: number) => void;
  onAddMeal: () => void;
  onUpdateFood: (mealIndex: number, foodIndex: number, patch: Partial<DietPlanMealEdit["foods"][number]>) => void;
  onRemoveFood: (mealIndex: number, foodIndex: number) => void;
  onAddFood: (mealIndex: number) => void;
  onSave: () => void;
  onCancel: () => void;
  busy: boolean;
}) {
  return <div className="space-y-4 rounded-lg border border-blue-200 bg-blue-50/40 p-4">
    <p className="text-xs font-semibold text-blue-700">Modo edición</p>
    {meals.map((meal, mi) => <div key={mi} className="space-y-2 rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <input className={inputClass} style={{ maxWidth: 140 }} value={meal.mealType} placeholder="Tipo"
          onChange={event => onUpdateMeal(mi, { mealType: event.target.value })} />
        <input className={inputClass} value={meal.name} placeholder="Nombre de la comida"
          onChange={event => onUpdateMeal(mi, { name: event.target.value })} />
        <button type="button" className="text-xs font-semibold text-red-600" onClick={() => onRemoveMeal(mi)}>Eliminar comida</button>
      </div>
      <div className="space-y-2">
        {meal.foods.map((food, fi) => <div key={fi} className="grid grid-cols-2 gap-2 rounded border border-slate-100 p-2 sm:grid-cols-6">
          <input className={`${inputClass} sm:col-span-2`} value={food.foodName} placeholder="Alimento"
            onChange={event => onUpdateFood(mi, fi, { foodName: event.target.value })} />
          <input className={inputClass} type="number" min={0} step="any" value={food.quantity} placeholder="Cantidad"
            onChange={event => onUpdateFood(mi, fi, { quantity: Number(event.target.value) })} />
          <input className={inputClass} value={food.unit} placeholder="Unidad"
            onChange={event => onUpdateFood(mi, fi, { unit: event.target.value })} />
          <input className={inputClass} type="number" min={0} step="any" value={food.calories ?? ""} placeholder="kcal"
            onChange={event => onUpdateFood(mi, fi, { calories: event.target.value === "" ? null : Number(event.target.value) })} />
          <button type="button" className="text-xs font-semibold text-red-600" onClick={() => onRemoveFood(mi, fi)}>Quitar</button>
        </div>)}
        <button type="button" className={secondaryButton} onClick={() => onAddFood(mi)}>Agregar alimento</button>
      </div>
    </div>)}
    <button type="button" className={secondaryButton} onClick={onAddMeal}>Agregar comida</button>
    <div className="flex gap-3 border-t border-blue-100 pt-3">
      <button type="button" className={primaryButton} onClick={onSave} disabled={busy}>{busy ? "Guardando…" : "Guardar cambios"}</button>
      <button type="button" className={secondaryButton} onClick={onCancel} disabled={busy}>Cancelar</button>
    </div>
  </div>;
}

function ConfirmApprove({ onConfirm, onCancel, busy }: { onConfirm: () => void; onCancel: () => void; busy: boolean }) {
  return <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
    <p className="text-xs text-slate-700">Al aprobar este plan quedará registrado como versión final revisada por el profesional.</p>
    <div className="flex gap-3">
      <button className={primaryButton} onClick={onConfirm} disabled={busy}>{busy ? "Aprobando…" : "Confirmar"}</button>
      <button className={secondaryButton} onClick={onCancel} disabled={busy}>Cancelar</button>
    </div>
  </div>;
}

function RejectForm({ reason, onChange, onConfirm, onCancel, busy }: {
  reason: string; onChange: (value: string) => void; onConfirm: () => void; onCancel: () => void; busy: boolean;
}) {
  return <div className="space-y-3 rounded-lg border border-red-200 bg-red-50/40 p-4">
    <label className="block text-xs font-semibold text-slate-600">
      Indica brevemente por qué se rechaza este borrador.
      <textarea className={`mt-1 ${inputClass}`} rows={2} value={reason} onChange={event => onChange(event.target.value)} />
    </label>
    <div className="flex gap-3">
      <button className={dangerSolidButton} onClick={onConfirm} disabled={busy || !reason.trim()}>
        {busy ? "Rechazando…" : "Confirmar rechazo"}
      </button>
      <button className={secondaryButton} onClick={onCancel} disabled={busy}>Cancelar</button>
    </div>
  </div>;
}

function RegenerateForm({ instructions, onChange, onConfirm, onCancel, busy }: {
  instructions: string; onChange: (value: string) => void; onConfirm: () => void; onCancel: () => void; busy: boolean;
}) {
  return <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
    <label className="block text-xs font-semibold text-slate-600">
      Instrucciones adicionales para el nuevo borrador (opcional)
      <textarea className={`mt-1 ${inputClass}`} rows={2} maxLength={500}
        placeholder="Ej. Evitar lácteos, usar preparaciones más sencillas" value={instructions}
        onChange={event => onChange(event.target.value)} />
    </label>
    <div className="flex gap-3">
      <button className={primaryButton} onClick={onConfirm} disabled={busy}>{busy ? "Generando nueva versión…" : "Generar nueva versión"}</button>
      <button className={secondaryButton} onClick={onCancel} disabled={busy}>Cancelar</button>
    </div>
  </div>;
}
