import type { CaptureOptions, Patient, PatientCreate, PatientUpdate, Consultation, ConsultationCreate, ConsultationUpdate, LegacyPlan, KnowledgeSource, KnowledgeSourceCreate, DietPlanGenerationResult, DietPlanDetail, DietPlanEditRequest, PlanTraceability, EvaluationMetrics, AssistantChatRequest, AssistantChatResponse, GenerationJobStarted, GenerationStatus, DashboardSummary } from "./types";
export type * from "./types";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public status: number, public existingId?: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, cache: "no-store", headers: { "Content-Type": "application/json", ...init.headers } });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("No fue posible conectar con el servidor. Verifica la conexión e inténtalo de nuevo.", 0);
  }
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null);
    // El backend de administración de fuentes usa `detail` (HTTPException estándar de FastAPI)
    // en vez de `message`; se acepta cualquiera de los dos sin romper el resto de la app.
    const messageField = typeof data === "object" && data !== null && "message" in data && typeof data.message === "string"
      ? data.message : typeof data === "object" && data !== null && "detail" in data && typeof data.detail === "string" ? data.detail : null;
    const safe = response.status < 500 && messageField !== null;
    const message = safe ? messageField as string : "No fue posible cargar o guardar los datos. Inténtalo de nuevo.";
    const existingId = typeof data === "object" && data !== null && "existingId" in data && typeof data.existingId === "string" ? data.existingId : undefined;
    throw new ApiError(message, response.status, existingId);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function requestForm<T>(path: string, formData: FormData, method: string = "POST"): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { method, body: formData, cache: "no-store" });
  } catch {
    throw new ApiError("No fue posible conectar con el servidor. Verifica la conexión e inténtalo de nuevo.", 0);
  }
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null);
    const messageField = typeof data === "object" && data !== null && "detail" in data && typeof data.detail === "string"
      ? data.detail : typeof data === "object" && data !== null && "message" in data && typeof data.message === "string" ? data.message : null;
    const message = response.status < 500 && messageField !== null ? messageField : "No fue posible completar la operación. Inténtalo de nuevo.";
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export const getCaptureOptions = (signal?: AbortSignal) => request<CaptureOptions>("/capture-options", { signal });
export const getDashboardSummary = (signal?: AbortSignal) => request<DashboardSummary>("/dashboard/summary", { signal });
export const getPatients = (signal?: AbortSignal) => request<Patient[]>("/patients", { signal });
export const getPatient = (id: string, signal?: AbortSignal) => request<Patient>(`/patients/${encodeURIComponent(id)}`, { signal });
export const createPatient = (data: PatientCreate, key: string) => request<Patient>("/patients", { method: "POST", headers: { "Idempotency-Key": key }, body: JSON.stringify(data) });
export const updatePatient = (id: string, data: PatientUpdate) => request<Patient>(`/patients/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(data) });
export const getPatientConsultations = (id: string, signal?: AbortSignal) => request<Consultation[]>(`/patients/${encodeURIComponent(id)}/consultations`, { signal });
export const createConsultation = (id: string, data: ConsultationCreate, key: string) => request<Consultation>(`/patients/${encodeURIComponent(id)}/consultations`, { method: "POST", headers: { "Idempotency-Key": key }, body: JSON.stringify(data) });
export const getConsultation = (id: string, signal?: AbortSignal) => request<Consultation>(`/consultations/${encodeURIComponent(id)}`, { signal });
export const updateConsultation = (id: string, data: ConsultationUpdate) => request<Consultation>(`/consultations/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(data) });
export const calculateConsultation = (id: string) => request<Consultation>(`/consultations/${encodeURIComponent(id)}/calculate`, { method: "POST" });
export const generateDraft = (consultationId: string) => request<DietPlanGenerationResult>(`/consultations/${encodeURIComponent(consultationId)}/generate-draft`, { method: "POST" });
// Progreso por etapas real (corrección de UX): /start responde de inmediato con el id;
// el llamador hace polling de getGenerationStatus en vez de esperar bloqueado varios minutos.
export const startGenerateDraft = (consultationId: string) => request<GenerationJobStarted>(`/consultations/${encodeURIComponent(consultationId)}/generate-draft/start`, { method: "POST" });
export const getGenerationStatus = (generationId: string, signal?: AbortSignal) => request<GenerationStatus>(`/generations/${encodeURIComponent(generationId)}/status`, { signal });
export const getPlan = (planId: string, signal?: AbortSignal) => request<DietPlanDetail>(`/plans/${encodeURIComponent(planId)}`, { signal });
export const getConsultationPlans = (consultationId: string, signal?: AbortSignal) => request<DietPlanDetail[]>(`/consultations/${encodeURIComponent(consultationId)}/plans`, { signal });
export const editPlan = (planId: string, data: DietPlanEditRequest) => request<DietPlanDetail>(`/plans/${encodeURIComponent(planId)}`, { method: "PATCH", body: JSON.stringify(data) });
export const approvePlan = (planId: string, actor?: string) => request<DietPlanDetail>(`/plans/${encodeURIComponent(planId)}/approve`, { method: "POST", body: JSON.stringify({ actor: actor || null }) });
export const rejectPlan = (planId: string, reason: string, actor?: string) => request<DietPlanDetail>(`/plans/${encodeURIComponent(planId)}/reject`, { method: "POST", body: JSON.stringify({ reason, actor: actor || null }) });
export const regeneratePlan = (planId: string, instructions?: string, actor?: string) => request<DietPlanGenerationResult>(`/plans/${encodeURIComponent(planId)}/regenerate`, { method: "POST", body: JSON.stringify({ instructions: instructions || null, actor: actor || null }) });
export const startRegeneratePlan = (planId: string, instructions?: string, actor?: string) => request<GenerationJobStarted>(`/plans/${encodeURIComponent(planId)}/regenerate/start`, { method: "POST", body: JSON.stringify({ instructions: instructions || null, actor: actor || null }) });
export const getPlans = () => request<LegacyPlan[]>("/plans");
export const getSources = (signal?: AbortSignal) => request<KnowledgeSource[]>("/sources", { signal });
export const getSource = (id: string, signal?: AbortSignal) => request<KnowledgeSource>(`/sources/${encodeURIComponent(id)}`, { signal });
export function createSource(data: KnowledgeSourceCreate): Promise<KnowledgeSource> {
  const form = new FormData();
  form.set("file", data.file);
  form.set("name", data.name);
  if (data.institution) form.set("institution", data.institution);
  if (data.version) form.set("version", data.version);
  form.set("sourceType", data.sourceType);
  if (data.publicationDate) form.set("publicationDate", data.publicationDate);
  return requestForm<KnowledgeSource>("/sources", form);
}
export const deleteSource = (id: string) => request<void>(`/sources/${encodeURIComponent(id)}`, { method: "DELETE" });
export const reindexSource = (id: string) => request<KnowledgeSource>(`/sources/${encodeURIComponent(id)}/reindex`, { method: "POST" });
export const sourceDocumentUrl = (id: string) => `${API_BASE}/sources/${encodeURIComponent(id)}/document`;
export function downloadSourceDocument(id: string, suggestedName?: string): Promise<void> {
  return fetch(`${API_BASE}/sources/${encodeURIComponent(id)}/download`, { cache: "no-store" }).then(async response => {
    if (!response.ok) {
      const data: unknown = await response.json().catch(() => null);
      const message = typeof data === "object" && data !== null && "detail" in data && typeof data.detail === "string"
        ? data.detail : "No fue posible descargar el documento.";
      throw new ApiError(message, response.status);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = suggestedName || `documento-${id}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });
}
export const getPlanTraceability = (planId: string, signal?: AbortSignal) => request<PlanTraceability>(`/plans/${encodeURIComponent(planId)}/traceability`, { signal });
export const getPlanEvaluationMetrics = (planId: string, signal?: AbortSignal) => request<EvaluationMetrics>(`/plans/${encodeURIComponent(planId)}/evaluation-metrics`, { signal });
// El modelo local puede tardar varios minutos (sección 28): sin timeout propio, se deja al navegador/usuario (cerrar el panel).
export const assistantChat = (data: AssistantChatRequest, signal?: AbortSignal) => request<AssistantChatResponse>("/assistant/chat", { method: "POST", body: JSON.stringify(data), signal });

export async function downloadPlanPdf(planId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/plans/${encodeURIComponent(planId)}/export/pdf`, { cache: "no-store" });
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null);
    const message = typeof data === "object" && data !== null && "message" in data && typeof data.message === "string"
      ? data.message : "No fue posible exportar el plan a PDF.";
    throw new ApiError(message, response.status);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `plan-${planId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}
