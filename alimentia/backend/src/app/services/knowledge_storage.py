"""
Validación y almacenamiento físico de documentos de la base de conocimiento
(administración de fuentes RAG).

Principio (sección 14 del pedido): el frontend NUNCA envía ni recibe una
ruta física. Solo `source_id`. Este módulo es el único que sabe traducir un
nombre de archivo físico a una ruta real dentro de `ALIMENTIA_KNOWLEDGE_PATH`,
y siempre verifica que la ruta resuelta quede dentro de ese directorio
(nunca sirve ni acepta un archivo fuera de la carpeta autorizada).
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
    """Archivo o metadata inválida (sección 34): nunca se acepta un archivo
    solo porque termina en .pdf."""


def max_file_size_bytes() -> int:
    mb = int(os.getenv("ALIMENTIA_MAX_KNOWLEDGE_FILE_MB", "50"))
    return mb * 1024 * 1024


def validate_pdf(*, filename: str, content_type: str | None, data: bytes) -> None:
    """Valida extensión, MIME, tamaño y firma real del archivo. Nunca ejecuta
    ni interpreta el contenido del documento (sección 34)."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(f"Formato de archivo no admitido ('{ext or 'sin extensión'}'). Solo se admite PDF.")
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise FileValidationError(f"Tipo de archivo no admitido ('{content_type}'). Solo se admite application/pdf.")
    if not data:
        raise FileValidationError("El archivo está vacío.")
    if len(data) > max_file_size_bytes():
        raise FileValidationError(
            f"El archivo excede el tamaño máximo permitido ({max_file_size_bytes() // (1024 * 1024)} MB).")
    if not data.startswith(PDF_SIGNATURE):
        raise FileValidationError("El archivo no tiene una firma PDF válida (encabezado %PDF- ausente).")


def slugify(name: str) -> str:
    """Slug ASCII simple y estable para usar como manifestSourceId/nombre de
    archivo físico. Nunca infiere significado del nombre: es solo una
    normalización de caracteres."""
    normalized = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "fuente"


def sanitize_display_filename(filename: str) -> str:
    """Sanitiza el nombre original para uso seguro en Content-Disposition:
    quita separadores de ruta y caracteres de control; conserva el resto tal
    cual para que la descarga se vea con el nombre real del documento."""
    name = Path(filename or "documento.pdf").name
    name = re.sub(r"[\x00-\x1f\"\\]", "", name).strip()
    return name or "documento.pdf"


def generate_stored_filename(base_slug: str, ext: str = ".pdf") -> str:
    """Sección 35: `{sourceSlug}__{uuid}.pdf`. Nunca se usa el nombre original
    como identificador interno -evita colisiones y cualquier ambigüedad con
    caracteres especiales del filesystem-."""
    return f"{base_slug}__{uuid.uuid4().hex}{ext}"


def resolve_stored_path(stored_filename: str) -> Path:
    """Traduce un nombre de archivo físico a una ruta real, verificando que
    quede dentro de `ALIMENTIA_KNOWLEDGE_PATH` (sección 14: nunca se sirve ni
    acepta un archivo fuera de la carpeta autorizada; previene path
    traversal aunque `stored_filename` nunca venga directamente del
    frontend)."""
    base = knowledge_path().resolve()
    candidate = (base / stored_filename).resolve()
    if base not in candidate.parents:
        raise FileValidationError("Ruta de archivo fuera del directorio autorizado.")
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
