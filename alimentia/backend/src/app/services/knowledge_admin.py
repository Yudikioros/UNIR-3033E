"""
Administración de documentos de la base de conocimiento RAG (alta,
eliminación, reintento de indexación).

Mantiene sincronizados los cuatro lugares que deben coincidir siempre:

    ARCHIVO FÍSICO ↔ MANIFEST ↔ KnowledgeSource ↔ QDRANT

Principio: nunca se deja el sistema "fingiendo que todo está correcto". Si
falla la indexación de una fuente nueva, se revierte todo lo que ya se había
hecho (archivo, manifiesto, fila); si el rollback mismo falla a mitad de
camino, la fuente queda en estado ERROR (nunca en un estado ambiguo) para
que un profesional pueda reintentar o eliminarla explícitamente.
"""
from datetime import datetime, timezone

from app.repositories import knowledge as knowledge_repo
from app.schemas.knowledge import KnowledgeSourceRead
from app.services import knowledge_manifest, knowledge_storage, rag_engine

VALID_SOURCE_TYPES = knowledge_manifest.VALID_SOURCE_TYPES
DUPLICATE_MESSAGE = "Este documento ya se encuentra registrado en la base de conocimiento."


class KnowledgeAdminError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _parse_publication_date(value: str | None):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise KnowledgeAdminError(422, "Fecha de publicación inválida (se espera formato AAAA-MM-DD).") from None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


async def add_source(db, *, file_bytes: bytes, upload_filename: str, content_type: str | None,
                      name: str, institution: str | None, version: str | None,
                      source_type: str, publication_date: str | None) -> KnowledgeSourceRead:
    """Flujo de alta transaccional (sección 6): valida, comprueba duplicados,
    guarda el archivo, registra manifiesto + KnowledgeSource, indexa, y
    verifica -antes de devolver la fuente como disponible- que realmente
    quedó indexada. Cualquier fallo revierte lo ya hecho."""
    # 1) Validar archivo.
    try:
        knowledge_storage.validate_pdf(filename=upload_filename, content_type=content_type, data=file_bytes)
    except knowledge_storage.FileValidationError as exc:
        raise KnowledgeAdminError(422, str(exc)) from None

    # 2) Validar metadata.
    name = (name or "").strip()
    if not name:
        raise KnowledgeAdminError(422, "El nombre de la fuente es obligatorio.")
    if source_type not in VALID_SOURCE_TYPES:
        raise KnowledgeAdminError(422, f"Tipo de fuente inválido. Valores admitidos: {', '.join(sorted(VALID_SOURCE_TYPES))}.")
    parsed_publication_date = _parse_publication_date(publication_date)

    # 3) Generar manifestSourceId seguro.
    base_slug = knowledge_storage.slugify(name)
    manifest_source_id = knowledge_manifest.next_manifest_source_id(base_slug)

    # 4) Comprobar duplicados por checksum (nunca solo por nombre de archivo).
    checksum = knowledge_repo.checksum_bytes(file_bytes)
    duplicate = await knowledge_repo.find_active_by_checksum(db, checksum)
    if duplicate is not None:
        raise KnowledgeAdminError(409, DUPLICATE_MESSAGE)

    # 5) Guardar archivo.
    stored_filename = knowledge_storage.generate_stored_filename(base_slug)
    display_filename = knowledge_storage.sanitize_display_filename(upload_filename)
    knowledge_storage.save_file(stored_filename, file_bytes)

    # 6) Registrar en el manifiesto.
    manifest_entry = {
        "id": manifest_source_id, "name": name, "institution": institution or None,
        "version": version or None, "file": stored_filename, "type": source_type, "active": True,
        "scope": ["adult_general"],
    }
    if parsed_publication_date:
        manifest_entry["publicationYear"] = parsed_publication_date.year
    try:
        knowledge_manifest.add_source_entry(manifest_entry)
    except knowledge_manifest.ManifestError as exc:
        knowledge_storage.delete_file(stored_filename)
        raise KnowledgeAdminError(500, f"No fue posible registrar la fuente en el manifiesto: {exc}") from None

    # 7) Sincronizar KnowledgeSource (estado inicial: INDEXING).
    try:
        row = await knowledge_repo.create_pending_source(
            db, manifest_source_id=manifest_source_id, document_name=name, institution=institution or None,
            version=version or None, source_type=source_type, publication_date=parsed_publication_date,
            original_filename=display_filename, stored_filename=stored_filename, checksum=checksum)
    except Exception as exc:
        _rollback(stored_filename=stored_filename, manifest_source_id=manifest_source_id, db_row_id=None)
        raise KnowledgeAdminError(500, f"No fue posible registrar la fuente: {exc}") from None

    # 8-9) Indexar y verificar.
    outcome = await _index_and_verify(manifest_source_id=manifest_source_id, name=name, institution=institution,
                                       version=version, stored_filename=stored_filename)
    if outcome["status"] != "indexed":
        rolled_back = _rollback(stored_filename=stored_filename, manifest_source_id=manifest_source_id, db_row_id=None)
        if rolled_back:
            await knowledge_repo.delete_source_row(db, row.id)
            raise KnowledgeAdminError(502, outcome["message"] or "No fue posible indexar el documento.")
        # El rollback completo no fue posible (sección 11): se deja la fuente
        # registrada en estado ERROR para que pueda reintentarse o eliminarse
        # explícitamente, en vez de fingir que quedó disponible.
        await knowledge_repo.mark_index_error(db, row.id, outcome["message"] or "Error de indexación desconocido.")
        raise KnowledgeAdminError(502, outcome["message"] or "No fue posible indexar el documento.")

    await knowledge_repo.mark_indexed(db, row.id)
    return await knowledge_repo.get_source(db, row.id)


async def _index_and_verify(*, manifest_source_id: str, name: str, institution: str | None,
                             version: str | None, stored_filename: str) -> dict:
    path = knowledge_storage.resolve_stored_path(stored_filename)
    source = {"id": manifest_source_id, "name": name, "institution": institution or None,
              "version": version or None, "scope": ["adult_general"], "path": path}
    return rag_engine.index_source(source)


def _rollback(*, stored_filename: str, manifest_source_id: str, db_row_id: str | None) -> bool:
    """Revierte archivo + manifiesto (sección 11). Devuelve True si el
    rollback se completó sin errores; False si algo falló a mitad de camino
    (en cuyo caso el llamador debe dejar la fuente en estado ERROR en vez de
    borrarla, para no perder rastro de un archivo que pudo haber quedado)."""
    try:
        knowledge_storage.delete_file(stored_filename)
        knowledge_manifest.remove_source_entry(manifest_source_id)
        return True
    except Exception:
        return False


async def reindex_source(db, source_id: str) -> KnowledgeSourceRead:
    """Sección 22: reintenta indexar una fuente que quedó en ERROR (o
    re-verifica una que ya estaba INDEXED). Nunca reconstruye toda la
    colección: solo esta fuente."""
    try:
        row = await knowledge_repo.get_source_row(db, source_id)
    except knowledge_repo.KnowledgeSourceNotFound:
        raise KnowledgeAdminError(404, "No se encontró la fuente de conocimiento.") from None
    if not row.isActive or not row.storedFilename or not row.manifestSourceId:
        raise KnowledgeAdminError(409, "Esta fuente no tiene un archivo activo que pueda reindexarse.")

    outcome = await _index_and_verify(manifest_source_id=row.manifestSourceId, name=row.documentName,
                                       institution=row.institution, version=row.version,
                                       stored_filename=row.storedFilename)
    if outcome["status"] != "indexed":
        await knowledge_repo.mark_index_error(db, source_id, outcome["message"] or "Error de indexación desconocido.")
        raise KnowledgeAdminError(502, outcome["message"] or "No fue posible indexar el documento.")
    await knowledge_repo.mark_indexed(db, source_id)
    return await knowledge_repo.get_source(db, source_id)


async def delete_source(db, source_id: str) -> None:
    """Sección 15-19: "Eliminar" desde la UI puede significar, internamente,
    DESACTIVAR (cuando hay historial real de planes que citaron la fuente) en
    vez de borrar físicamente -la FK de `RetrievedSource` ya lo exige, pero
    se decide aquí explícitamente para poder limpiar Qdrant/archivo/manifest
    de forma coherente en ambos casos.

    Comportamiento exacto:
    - Sin historial: se borra la fila, el archivo físico y la entrada del
      manifiesto (no queda ningún rastro huérfano).
    - Con historial: la fila se conserva con `isActive=false` (nunca se
      destruye la trazabilidad de qué fuente usó un plan aprobado en el
      pasado), el archivo físico se elimina de la biblioteca activa, y el
      manifiesto marca la entrada `active: false` en vez de borrarla.
    En ambos casos, los chunks de Qdrant se eliminan siempre: una fuente
    eliminada nunca vuelve a aparecer en búsquedas RAG nuevas.
    """
    try:
        row = await knowledge_repo.get_source_row(db, source_id)
    except knowledge_repo.KnowledgeSourceNotFound:
        raise KnowledgeAdminError(404, "No se encontró la fuente de conocimiento.") from None

    manifest_source_id = row.manifestSourceId
    if not manifest_source_id:
        manifest = knowledge_manifest.load_manifest()
        entry = next((s for s in manifest["sources"] if s["file"] == row.originalFilename), None)
        manifest_source_id = entry["id"] if entry else None

    if manifest_source_id:
        try:
            rag_engine.delete_source_chunks(manifest_source_id)
        except Exception as exc:
            raise KnowledgeAdminError(502, f"No fue posible eliminar los fragmentos indexados de esta fuente: {exc}") from None

    has_history = await knowledge_repo.has_history(db, source_id)
    stored_filename = row.storedFilename or row.originalFilename

    if has_history:
        if manifest_source_id:
            knowledge_manifest.deactivate_source_entry(manifest_source_id)
        knowledge_storage.delete_file(stored_filename)
        await knowledge_repo.deactivate_source(db, source_id)
    else:
        if manifest_source_id:
            knowledge_manifest.remove_source_entry(manifest_source_id)
        knowledge_storage.delete_file(stored_filename)
        await knowledge_repo.delete_source_row(db, source_id)
