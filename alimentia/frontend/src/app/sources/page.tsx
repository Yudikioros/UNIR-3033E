"use client";
import { useEffect, useRef, useState } from "react";
import { BookOpen, Download, Eye, Loader2, Plus, RefreshCw, Trash2, X } from "lucide-react";
import { getSources, createSource, deleteSource, reindexSource, downloadSourceDocument, sourceDocumentUrl, errorMessage } from "../../services/api";
import type { KnowledgeSource, SourceType } from "../../services/types";
import { Notice, primaryButton, secondaryButton } from "../../components/capture/fields";

const TYPE_LABELS: Record<SourceType, string> = {
  GUIDELINE: "Guía", REFERENCE_TABLE: "Tabla de referencia", REGULATION: "Normativa", OTHER: "Otro",
};
const TYPE_OPTIONS: SourceType[] = ["GUIDELINE", "REFERENCE_TABLE", "REGULATION", "OTHER"];
const dangerSolidButton = "inline-flex items-center justify-center rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50";
const iconButton = "inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-40";

function dateLabel(value: string | null): string {
  return value ? new Date(value).toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" }) : "—";
}

export default function SourcesPage() {
  const [sources, setSources] = useState<KnowledgeSource[]>();
  const [error, setError] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeSource>();
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [reindexingId, setReindexingId] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    getSources(controller.signal)
      .then(setSources)
      .catch(err => { if (!controller.signal.aborted) setError(errorMessage(err, "No fue posible cargar las fuentes de conocimiento.")); });
    return () => controller.abort();
  }, []);

  function handleCreated(source: KnowledgeSource) {
    setShowAdd(false);
    setSources(current => current ? [source, ...current] : [source]);
  }

  async function handleDeleteConfirm() {
    if (!deleteTarget || deleting) return;
    setDeleting(true); setDeleteError("");
    try {
      await deleteSource(deleteTarget.id);
      setSources(current => current?.filter(s => s.id !== deleteTarget.id));
      setDeleteTarget(undefined);
    } catch (err) {
      setDeleteError(errorMessage(err, "No fue posible eliminar la fuente."));
    } finally {
      setDeleting(false);
    }
  }

  async function handleReindex(source: KnowledgeSource) {
    setReindexingId(source.id); setError("");
    try {
      const updated = await reindexSource(source.id);
      setSources(current => current?.map(s => (s.id === updated.id ? updated : s)));
    } catch (err) {
      setError(errorMessage(err, "No fue posible reintentar la indexación."));
    } finally {
      setReindexingId(undefined);
    }
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F8FAFC] overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-8 py-5 flex justify-between items-center flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Fuentes</h1>
          <p className="text-xs text-slate-500 mt-1">
            Biblioteca autorizada que alimenta la base de conocimiento (RAG). El
            modelo de lenguaje sólo puede citar documentos de esta lista.
          </p>
        </div>
        {sources && sources.length > 0 ? (
          <button className={primaryButton} onClick={() => setShowAdd(true)}>
            <Plus size={16} /> Agregar fuente
          </button>
        ) : null}
      </header>

      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        <div className="max-w-7xl mx-auto space-y-4">
          {error ? <Notice error>{error}</Notice> : null}
          {!sources && !error ? (
            <p role="status" className="py-8 text-center text-sm text-slate-400">Cargando fuentes…</p>
          ) : sources && sources.length === 0 ? (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-12 text-center space-y-4">
              <BookOpen size={28} className="mx-auto text-slate-300" />
              <div>
                <p className="text-sm text-slate-500">No hay fuentes de conocimiento configuradas.</p>
                <p className="text-xs text-slate-400 mt-1">Agrega documentos para habilitar consultas documentales mediante RAG.</p>
              </div>
              <button className={primaryButton} onClick={() => setShowAdd(true)}>
                <Plus size={16} /> Agregar fuente
              </button>
            </div>
          ) : sources ? (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/50 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <th className="py-3.5 px-6">Fuente</th>
                    <th className="py-3.5 px-6">Institución</th>
                    <th className="py-3.5 px-6">Versión</th>
                    <th className="py-3.5 px-6">Tipo</th>
                    <th className="py-3.5 px-6">Fecha</th>
                    <th className="py-3.5 px-6">Estado</th>
                    <th className="py-3.5 px-6">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
                  {sources.map(source => (
                    <SourceRow key={source.id} data={source} reindexing={reindexingId === source.id}
                      onDelete={() => setDeleteTarget(source)} onReindex={() => handleReindex(source)} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>

      {showAdd ? <AddSourceModal onClose={() => setShowAdd(false)} onCreated={handleCreated} /> : null}
      {deleteTarget ? (
        <DeleteConfirmDialog name={deleteTarget.documentName} busy={deleting} error={deleteError}
          onCancel={() => { setDeleteTarget(undefined); setDeleteError(""); }} onConfirm={handleDeleteConfirm} />
      ) : null}
    </div>
  );
}

function StatusBadge({ data }: { data: KnowledgeSource }) {
  if (data.indexStatus === "INDEXING") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider bg-blue-50 text-blue-700 border border-blue-200">
        <Loader2 size={10} className="animate-spin" /> Indexando
      </span>
    );
  }
  if (data.indexStatus === "ERROR") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider bg-red-50 text-red-700 border border-red-200" title={data.indexError ?? undefined}>
        <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span> Error de indexación
      </span>
    );
  }
  if (data.isActive && data.indexStatus === "INDEXED") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider bg-green-50 text-green-700 border border-green-200">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span> Vigente
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider bg-slate-100 text-slate-500 border border-slate-200">
      <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span> Inactiva
    </span>
  );
}

function SourceRow({ data, reindexing, onDelete, onReindex }: {
  data: KnowledgeSource; reindexing: boolean; onDelete: () => void; onReindex: () => void;
}) {
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  async function handleDownload() {
    if (downloading) return;
    setDownloading(true); setDownloadError("");
    try {
      await downloadSourceDocument(data.id, data.originalFilename ?? undefined);
    } catch (err) {
      setDownloadError(errorMessage(err, "No fue posible descargar el documento."));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <tr className="hover:bg-slate-50/50 transition-colors">
      <td className="py-4 px-6 font-medium text-slate-800">
        <div className="flex items-center gap-3">
          <div className="bg-blue-50 p-2 rounded-xl text-blue-600 flex-shrink-0">
            <BookOpen size={16} />
          </div>
          <span>{data.documentName}</span>
        </div>
        {downloadError ? <p className="mt-1 text-[11px] text-red-600">{downloadError}</p> : null}
      </td>
      <td className="py-4 px-6 text-slate-600 text-sm">{data.institution ?? "—"}</td>
      <td className="py-4 px-6 text-slate-600 font-mono text-xs">{data.version ?? "—"}</td>
      <td className="py-4 px-6 text-slate-600 text-xs">{data.sourceType ? TYPE_LABELS[data.sourceType] : "—"}</td>
      <td className="py-4 px-6 text-slate-500 text-xs">{dateLabel(data.publicationDate)}</td>
      <td className="py-4 px-6">
        <div className="flex items-center gap-2">
          <StatusBadge data={data} />
          {data.indexStatus === "ERROR" ? (
            <button className="text-[11px] font-semibold text-blue-600 hover:underline disabled:opacity-50" onClick={onReindex} disabled={reindexing}>
              {reindexing ? <Loader2 size={12} className="inline animate-spin" /> : <RefreshCw size={12} className="inline" />} Reintentar
            </button>
          ) : null}
        </div>
      </td>
      <td className="py-4 px-6">
        <div className="flex items-center gap-1">
          <a className={iconButton} href={sourceDocumentUrl(data.id)} target="_blank" rel="noreferrer" title="Ver documento" aria-label="Ver documento">
            <Eye size={15} />
          </a>
          <button className={iconButton} onClick={handleDownload} disabled={downloading} title="Descargar" aria-label="Descargar documento">
            {downloading ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
          </button>
          <button className={`${iconButton} hover:bg-red-50 hover:text-red-600`} onClick={onDelete} title="Eliminar" aria-label="Eliminar fuente">
            <Trash2 size={15} />
          </button>
        </div>
      </td>
    </tr>
  );
}

function DeleteConfirmDialog({ name, busy, error, onCancel, onConfirm }: {
  name: string; busy: boolean; error: string; onCancel: () => void; onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4">
        <div>
          <p className="text-sm font-bold text-slate-800">¿Eliminar esta fuente?</p>
          <p className="mt-2 text-xs text-slate-600">
            Se eliminará el documento «{name}» de la biblioteca y dejará de estar disponible para las
            consultas del asistente y del RAG.
          </p>
        </div>
        {error ? <Notice error>{error}</Notice> : null}
        {busy ? <p className="text-xs text-slate-500">Retirando documento de la base de conocimiento…</p> : null}
        <div className="flex justify-end gap-3 pt-2">
          <button className={secondaryButton} onClick={onCancel} disabled={busy}>Cancelar</button>
          <button className={dangerSolidButton} onClick={onConfirm} disabled={busy}>
            {busy ? "Eliminando…" : "Eliminar fuente"}
          </button>
        </div>
      </div>
    </div>
  );
}

function AddSourceModal({ onClose, onCreated }: { onClose: () => void; onCreated: (source: KnowledgeSource) => void }) {
  const [file, setFile] = useState<File>();
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const [version, setVersion] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("GUIDELINE");
  const [publicationDate, setPublicationDate] = useState("");
  const [nameTouched, setNameTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFile(selected: File | undefined) {
    setFile(selected);
    if (selected && !nameTouched) {
      setName(selected.name.replace(/\.pdf$/i, ""));
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !file || !name.trim()) return;
    setBusy(true); setError("");
    // El alta es una sola operación en el backend (validar, guardar, registrar
    // e indexar); no hay progreso granular real que consultar por polling, así
    // que se muestra la única etapa real disponible mientras dura la llamada
    // (sección 27), nunca un porcentaje inventado.
    setStage("Subiendo y procesando documento… puede tardar unos segundos.");
    try {
      const created = await createSource({
        file, name: name.trim(), institution: institution.trim() || undefined, version: version.trim() || undefined,
        sourceType, publicationDate: publicationDate || undefined,
      });
      onCreated(created);
    } catch (err) {
      setError(errorMessage(err, "No fue posible agregar la fuente."));
    } finally {
      setBusy(false); setStage("");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl space-y-4 max-h-[90vh] overflow-y-auto custom-scrollbar">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-bold text-slate-800">Agregar fuente</p>
            <p className="mt-1 text-xs text-slate-500">El documento se indexa automáticamente al registrarse.</p>
          </div>
          <button type="button" className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100" onClick={onClose} disabled={busy} aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <label className="block text-xs font-semibold text-slate-600">
            Documento (PDF) *
            <input ref={fileInputRef} type="file" accept="application/pdf,.pdf" required disabled={busy}
              onChange={event => handleFile(event.target.files?.[0])}
              className="mt-1.5 block w-full text-xs text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-blue-700 hover:file:bg-blue-100" />
          </label>
          <label className="block text-xs font-semibold text-slate-600">
            Nombre de la fuente *
            <input type="text" required disabled={busy} value={name}
              onChange={event => { setName(event.target.value); setNameTouched(true); }}
              className="mt-1.5 w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500" />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-xs font-semibold text-slate-600">
              Institución
              <input type="text" disabled={busy} value={institution} onChange={event => setInstitution(event.target.value)}
                className="mt-1.5 w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500" />
            </label>
            <label className="block text-xs font-semibold text-slate-600">
              Versión
              <input type="text" disabled={busy} value={version} onChange={event => setVersion(event.target.value)}
                className="mt-1.5 w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500" />
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-xs font-semibold text-slate-600">
              Tipo *
              <select required disabled={busy} value={sourceType} onChange={event => setSourceType(event.target.value as SourceType)}
                className="mt-1.5 w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500">
                {TYPE_OPTIONS.map(option => <option key={option} value={option}>{TYPE_LABELS[option]}</option>)}
              </select>
            </label>
            <label className="block text-xs font-semibold text-slate-600">
              Fecha de publicación
              <input type="date" disabled={busy} value={publicationDate} onChange={event => setPublicationDate(event.target.value)}
                className="mt-1.5 w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500" />
            </label>
          </div>

          {error ? <Notice error>{error}</Notice> : null}
          {busy && stage ? (
            <p className="flex items-center gap-2 text-xs text-blue-700">
              <Loader2 size={14} className="animate-spin" /> {stage}
            </p>
          ) : null}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" className={secondaryButton} onClick={onClose} disabled={busy}>Cancelar</button>
            <button type="submit" className={primaryButton} disabled={busy || !file || !name.trim()}>
              {busy ? "Agregando…" : "Agregar fuente"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
