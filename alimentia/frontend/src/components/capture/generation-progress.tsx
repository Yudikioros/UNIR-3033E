"use client";
import { useEffect, useState } from "react";
import type { GenerationJobStatus, GenerationStage } from "../../services/types";
import { primaryButton } from "./fields";

// Progreso por etapas real (corrección de UX): este orden y estos mensajes
// son los únicos que el backend puede reportar (GenerationStage en
// diet_plan_generation.py). Nada aquí se simula con temporizadores; el
// componente solo refleja lo que devuelve GET /generations/{id}/status.
const STAGES: { stage: GenerationStage; label: string }[] = [
  { stage: "VALIDATING", label: "Validando datos del paciente" },
  { stage: "LOADING_CALCULATIONS", label: "Recuperando requerimientos nutricionales" },
  { stage: "LOADING_FOOD_DATA", label: "Consultando información alimentaria" },
  { stage: "SEARCHING_KNOWLEDGE", label: "Consultando fuentes de conocimiento" },
  { stage: "BUILDING_CONTEXT", label: "Preparando información para generar el plan" },
  { stage: "GENERATING_WITH_LLM", label: "Generando borrador con IA" },
  { stage: "VALIDATING_RESPONSE", label: "Validando el borrador generado" },
  { stage: "PERSISTING", label: "Guardando el plan" },
];
const STAGE_INDEX = new Map(STAGES.map((entry, index) => [entry.stage, index]));

function elapsedLabel(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes} min ${seconds} s` : `${seconds} s`;
}

export function GenerationProgress({ status, stage, startedAt, error, onRetry }: {
  status: GenerationJobStatus; stage: GenerationStage | null; startedAt: string;
  error?: string | null; onRetry?: () => void;
}) {
  const [elapsedMs, setElapsedMs] = useState(() => Date.now() - new Date(startedAt).getTime());

  // Únicamente recalcula el tiempo transcurrido real cada segundo; nunca
  // decide la etapa ni el estado (eso viene siempre de `status`/`stage`,
  // obtenidos por polling real del backend).
  useEffect(() => {
    if (status !== "IN_PROGRESS") return;
    const interval = setInterval(() => setElapsedMs(Date.now() - new Date(startedAt).getTime()), 1000);
    return () => clearInterval(interval);
  }, [status, startedAt]);

  if (status === "FAILED") {
    return <div className="space-y-3 rounded-lg border border-red-200 bg-red-50 p-4">
      <p className="text-sm font-semibold text-red-700">Hubo un problema al generar el borrador.</p>
      <p className="text-xs text-red-700">{error || "No fue posible completar la generación. Intenta nuevamente."}</p>
      {onRetry ? <button className={primaryButton} onClick={onRetry}>Intentar nuevamente</button> : null}
    </div>;
  }

  const currentIndex = stage ? STAGE_INDEX.get(stage) ?? -1 : -1;
  const currentLabel = STAGES.find(entry => entry.stage === stage)?.label
    ?? (status === "SUCCESS" ? "Borrador generado correctamente" : "Preparando generación");

  return <div className="space-y-4 rounded-lg border border-blue-200 bg-blue-50/40 p-4">
    <div className="flex items-center gap-3">
      {status === "IN_PROGRESS" ? (
        <span aria-hidden className="h-4 w-4 flex-none animate-spin rounded-full border-2 border-blue-300 border-t-blue-600" />
      ) : (
        <span aria-hidden className="flex h-4 w-4 flex-none items-center justify-center rounded-full bg-green-600 text-[10px] font-bold text-white">✓</span>
      )}
      <p role="status" className="text-sm font-semibold text-blue-800">
        {status === "SUCCESS" ? "Borrador generado correctamente." : `${currentLabel}…`}
      </p>
    </div>

    <ol className="space-y-1.5 pl-1">
      {STAGES.map((entry, index) => {
        const done = status === "SUCCESS" || (currentIndex >= 0 && index < currentIndex);
        const active = status === "IN_PROGRESS" && index === currentIndex;
        return <li key={entry.stage} className="flex items-center gap-2 text-xs">
          <span aria-hidden className={`flex h-4 w-4 flex-none items-center justify-center rounded-full text-[10px] font-bold ${
            done ? "bg-green-600 text-white" : active ? "border-2 border-blue-500 text-blue-600" : "border border-slate-300 text-transparent"}`}>
            {done ? "✓" : active ? "•" : ""}
          </span>
          <span className={done ? "text-slate-500 line-through decoration-slate-300" : active ? "font-semibold text-blue-800" : "text-slate-400"}>
            {entry.label}
          </span>
        </li>;
      })}
    </ol>

    {status === "IN_PROGRESS" && stage === "GENERATING_WITH_LLM" ? (
      <p className="text-xs text-blue-700">Esta etapa puede tardar varios minutos cuando se utiliza el modelo local.</p>
    ) : null}

    {status === "IN_PROGRESS" ? (
      <p className="text-xs text-slate-500">Tiempo transcurrido: {elapsedLabel(elapsedMs)}</p>
    ) : null}
  </div>;
}
