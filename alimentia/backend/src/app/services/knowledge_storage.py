"""
Valida y almacena documentos dentro del directorio autorizado.

Las rutas físicas no se exponen al cliente y cada archivo resuelto debe
permanecer dentro del directorio de conocimiento.
"""
import os
import re
import unicodedata
import uuid
from pathlib import Path

from app.services.rag_engine import knowledge_path

ALLOWED_EXTENSIONS = {".pdf"}
ALLOWED_MIME_TYPES = {"application/pdf"}
PDF_SIGNATURE = b"%PDF-"


class FileValidationError(Exception):
    """El archivo no cumple las reglas de validación."""


def max_file_size_bytes() -> int:
    mb = int(os.getenv("ALIMENTIA_MAX_KNOWLEDGE_FILE_MB", "50"))
    return mb * 1024 * 1024


def validate_pdf(*, filename: str, content_type: str | None, data: bytes) -> None:
    """Valida extensión, tipo MIME, tamaño y firma del archivo."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Formato de archivo no admitido ('{ext or 'sin extensión'}'). Solo se admite PDF.")
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise FileValidationError(
            f"Tipo de archivo no admitido ('{content_type}'). Solo se admite application/pdf.")
    if not data:
        raise FileValidationError("El archivo está vacío.")
    if len(data) > max_file_size_bytes():
        raise FileValidationError(
            f"El archivo excede el tamaño máximo permitido ({max_file_size_bytes() // (1024 * 1024)} MB).")
    if not data.startswith(PDF_SIGNATURE):
        raise FileValidationError(
            "El archivo no tiene una firma PDF válida (encabezado %PDF- ausente).")


def slugify(name: str) -> str:
    """Normaliza un nombre para crear un identificador ASCII estable."""
    normalized = unicodedata.normalize("NFKD", name or "").encode(
        "ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "fuente"


def sanitize_display_filename(filename: str) -> str:
    """Elimina separadores y controles del nombre de descarga."""
    name = Path(filename or "documento.pdf").name
    name = re.sub(r"[\x00-\x1f\"\\]", "", name).strip()
    return name or "documento.pdf"


def generate_stored_filename(base_slug: str, ext: str = ".pdf") -> str:
    """Genera un nombre interno único a partir del slug y un UUID."""
    return f"{base_slug}__{uuid.uuid4().hex}{ext}"


def resolve_stored_path(stored_filename: str) -> Path:
    """Resuelve la ruta y rechaza archivos fuera del directorio autorizado."""
    base = knowledge_path().resolve()
    candidate = (base / stored_filename).resolve()
    if base not in candidate.parents:
        raise FileValidationError(
            "Ruta de archivo fuera del directorio autorizado.")
    return candidate


def save_file(stored_filename: str, data: bytes) -> Path:
    base = knowledge_path()
    base.mkdir(parents=True, exist_ok=True)
    path = resolve_stored_path(stored_filename)
    path.write_bytes(data)
    return path


def delete_file(stored_filename: str | None) -> None:
    """Elimina el archivo físico si existe. Nunca lanza excepción si ya no
    está (idempotente: puede llamarse durante un rollback o una eliminación
    repetida sin romper el flujo)."""
    if not stored_filename:
        return
    try:
        path = resolve_stored_path(stored_filename)
    except FileValidationError:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
