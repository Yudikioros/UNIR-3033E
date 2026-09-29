"use client";
import { Suspense, useEffect, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { assistantChat, getPlan, errorMessage } from "../../services/api";
import type { AssistantNavigationContext, AssistantSourceCitation } from "../../services/types";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: AssistantSourceCitation[];
}

function useNavigationContext(): AssistantNavigationContext {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const patientMatch = pathname.match(/^\/patients\/([^/?]+)/);
  const planMatch = pathname.match(/^\/plans\/([^/?]+)/);
  const patientId = patientMatch && patientMatch[1] !== "new" ? patientMatch[1] : null;
  const consultationParam = searchParams.get("consultation");
  const consultationId = consultationParam && consultationParam !== "new" ? consultationParam : null;
  const planId = planMatch ? planMatch[1] : null;
  return { route: pathname, patientId, consultationId, planId };
}

function suggestionsFor(context: AssistantNavigationContext): string[] {
  if (context.planId) {
    return ["¿Por qué este plan no se puede aprobar?", "¿Qué validaciones tiene?", "¿Qué cambió respecto a la versión anterior?"];
  }
  if (context.patientId) {
    return ["¿Cuál es su objetivo nutricional?", "¿Qué planes tiene?", "¿Cuál es su plan más reciente?"];
  }
  if (context.route === "/sources") {
    return ["¿Qué documentos están disponibles?"];
  }
  return ["¿Cuántos planes están aprobados?", "¿Qué pacientes tienen planes pendientes de revisión?"];
}

function ChatIcon() {
  return <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
      d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
  </svg>;
}

function FloatingAssistantInner() {
  const context = useNavigationContext();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [planVersion, setPlanVersion] = useState<number>();

  useEffect(() => {
    if (!open || !context.planId) return;
    const controller = new AbortController();
    getPlan(context.planId, controller.signal)
      .then(plan => { if (!controller.signal.aborted) setPlanVersion(plan.version); })
      .catch(() => {});
    return () => controller.abort();
  }, [open, context.planId]);

  async function send(question?: string) {
    const text = (question ?? input).trim();
    if (!text || sending) return;
    const conversation = messages.map(message => ({ role: message.role, content: message.content }));
    setMessages(current => [...current, { role: "user", content: text }]);
    setInput(""); setSending(true); setError("");
    try {
      const response = await assistantChat({ message: text, context, conversation });
      setMessages(current => [...current, { role: "assistant", content: response.answer, sources: response.sources }]);
    } catch (err) {
      setError(errorMessage(err, "No fue posible consultar al asistente en este momento."));
    } finally {
      setSending(false);
    }
  }

  const suggestions = suggestionsFor(context);

  return <>
    <button
      onClick={() => setOpen(current => !current)}
      title="Asistente AlimentIA"
      aria-label="Asistente AlimentIA"
      className="absolute bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg transition-transform hover:scale-105 hover:bg-blue-700"
    >
      <ChatIcon />
    </button>

    {open ? (
      <div className="absolute inset-y-0 right-0 z-50 flex w-full max-w-sm flex-col border-l border-slate-200 bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-sm font-bold text-slate-800">Asistente AlimentIA</p>
            <p className="mt-0.5 text-xs text-slate-500">Consulta información sobre pacientes, planes y fuentes.</p>
          </div>
          <button onClick={() => setOpen(false)} aria-label="Cerrar asistente" className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100">✕</button>
        </div>

        {context.planId || context.patientId ? (
          <div className="border-b border-slate-100 bg-slate-50 px-5 py-2 text-[11px] font-medium text-slate-500">
            Contexto: {context.planId ? `Plan actual${planVersion ? ` · Versión ${planVersion}` : ""}` : "Paciente actual"}
          </div>
        ) : null}

        <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4 custom-scrollbar">
          {messages.length === 0 ? (
            <div className="space-y-2">
              <p className="text-xs text-slate-400">Prueba preguntando:</p>
              {suggestions.map(question => (
                <button key={question} onClick={() => send(question)}
                  className="block w-full rounded-lg border border-slate-200 px-3 py-2 text-left text-xs text-slate-600 hover:bg-slate-50">
                  {question}
                </button>
              ))}
            </div>
          ) : null}

          {messages.map((message, index) => (
            <div key={index} className={message.role === "user" ? "text-right" : "text-left"}>
              <div className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-left text-xs ${message.role === "user" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-700"}`}>
                {message.content}
              </div>
              {message.role === "assistant" && message.sources && message.sources.length ? (
                <div className="mt-1 space-y-0.5 text-[10px] text-slate-400">
                  <p className="font-semibold uppercase tracking-wide">Fuentes consultadas</p>
                  {message.sources.map(source => (
                    <p key={source.sourceId}>{source.documentName}{source.institution ? ` — ${source.institution}` : ""}</p>
                  ))}
                </div>
              ) : null}
            </div>
          ))}

          {sending ? (
            <p className="text-xs text-slate-400">
              Consultando información en AlimentIA. La mayoría de las preguntas responden en segundos; algunas
              (explicaciones, comparaciones o búsquedas documentales) pueden tardar más porque usan el modelo local.
            </p>
          ) : null}
          {error ? <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-700">{error}</p> : null}
        </div>

        <form onSubmit={event => { event.preventDefault(); send(); }} className="flex items-center gap-2 border-t border-slate-200 p-3">
          <input
            value={input}
            onChange={event => setInput(event.target.value)}
            disabled={sending}
            placeholder="Pregunta sobre pacientes, planes o documentos…"
            className="flex-1 rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-xs outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-60"
          />
          <button type="submit" disabled={sending || !input.trim()}
            className="inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
            Enviar
          </button>
        </form>
      </div>
    ) : null}
  </>;
}

export function FloatingAssistant() {
  return <Suspense fallback={null}><FloatingAssistantInner /></Suspense>;
}
