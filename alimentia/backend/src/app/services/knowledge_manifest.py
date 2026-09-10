"""Manifiesto de fuentes autorizadas para el RAG (Fase 3.5).

El RAG nunca procesa un documento que no esté declarado aquí, y un documento
declarado que no exista en disco simplemente se ignora (sin excepción). Ver
PHASE3_5.md para el formato completo y cómo agregar una fuente real.
"""
import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger("uvicorn.error")

DEFAULT_MANIFEST_PATH = "/app/data/knowledge_base/manifest.json"
REQUIRED_SOURCE_FIELDS = ("id", "name", "file")
VALID_SOURCE_TYPES = {"GUIDELINE", "REFERENCE_TABLE", "REGULATION", "OTHER"}

# Sección 21: el prototipo es una sola instancia -no hace falta un lock
# distribuido-, pero dos requests concurrentes (alta + baja, o dos altas a la
# vez) sí pueden entrelazar su lectura-modificación-escritura del mismo
# archivo dentro del mismo proceso. Este lock serializa esa sección crítica.
_manifest_lock = threading.Lock()


def _manifest_path() -> Path:
    return Path(os.getenv("ALIMENTIA_KNOWLEDGE_MANIFEST_PATH", DEFAULT_MANIFEST_PATH))


def load_manifest() -> dict:
    """Devuelve {'version': str|None, 'sources': list[dict]}. Nunca lanza excepciones.

    Manifiesto ausente, ilegible o con formato inválido -> sin fuentes
    autorizadas (WARNING/ERROR según el caso), no detiene el arranque ni la
    ingesta.
    """
    path = _manifest_path()
    if not path.exists():
        logger.warning(
            "Manifiesto de conocimiento no encontrado en %s. No hay fuentes autorizadas todavía.", path)
        return {"version": None, "sources": []}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("Manifiesto de conocimiento en %s es ilegible o no es JSON válido: %s", path, exc)
        return {"version": None, "sources": []}

    if not isinstance(raw, dict) or not isinstance(raw.get("sources"), list):
        logger.error("Manifiesto de conocimiento en %s tiene un formato inválido (se esperaba un objeto con 'sources').", path)
        return {"version": None, "sources": []}

    version = raw.get("version") if isinstance(raw.get("version"), str) else None
    sources = []
    seen_ids = set()
    for entry in raw["sources"]:
        if not isinstance(entry, dict) or any(not entry.get(field) for field in REQUIRED_SOURCE_FIELDS):
            logger.error("Entrada de fuente inválida u omitida en el manifiesto (%s): %r", path, entry)
            continue
        source_id = str(entry["id"])
        if source_id in seen_ids:
            logger.error("Id de fuente duplicado en el manifiesto (%s): %s. Se omite la repetición.", path, source_id)
            continue
        seen_ids.add(source_id)
        source_type = entry.get("type", "GUIDELINE")
        if source_type not in VALID_SOURCE_TYPES:
            source_type = "OTHER"
        publication_year = entry.get("publicationYear")
        if not isinstance(publication_year, int):
            publication_year = None
        scope = entry.get("scope")
        if not isinstance(scope, list) or not all(isinstance(s, str) for s in scope):
            scope = []
        sources.append({
            "id": source_id,
            "name": str(entry["name"]),
            "institution": entry.get("institution") if isinstance(entry.get("institution"), str) else None,
            "version": entry.get("version") if isinstance(entry.get("version"), str) else None,
            "publicationYear": publication_year,
            "file": str(entry["file"]),
            "type": source_type,
            # Por defecto activo: los manifiestos existentes sin este campo
            # (Fase 3.5/4/5) siguen funcionando sin cambios.
            "active": bool(entry.get("active", True)),
            "scope": scope,
        })
    return {"version": version, "sources": sources}


def authorized_documents(knowledge_dir: Path) -> list[dict]:
    """Fuentes activas del manifiesto cuyo archivo existe en `knowledge_dir`.

    Cualquier archivo presente en `knowledge_dir` que no esté declarado en el
    manifiesto, cualquier fuente declarada cuyo archivo no exista, y
    cualquier fuente marcada `active: false` (referencia histórica, no se
    ingiere) se ignoran (no se procesan, no se lanza excepción).
    """
    manifest = load_manifest()
    authorized = []
    for source in manifest["sources"]:
        if not source["active"]:
            logger.info(
                "Fuente '%s' marcada como inactiva (referencia histórica): no se ingiere.", source["id"])
            continue
        path = knowledge_dir / source["file"]
        if path.exists() and path.is_file():
            authorized.append({**source, "path": path})
        else:
            logger.warning(
                "Fuente autorizada '%s' declara el archivo '%s' pero no se encontró en %s.",
                source["id"], source["file"], knowledge_dir)
    return authorized


def knowledge_base_version() -> Optional[str]:
    return load_manifest()["version"]


def authorized_source_count() -> int:
    return len(load_manifest()["sources"])


class ManifestError(Exception):
    """El manifiesto existe pero no es un JSON válido con la forma esperada;
    nunca se escribe sobre un archivo que no se puede interpretar con seguridad."""


def _read_raw() -> dict:
    """A diferencia de `load_manifest()` (que normaliza/filtra para lectura
    de solo lectura del RAG), esto devuelve la estructura tal cual está en
    disco -sin perder campos desconocidos- para poder reescribirla con
    seguridad. Manifiesto ausente -> estructura vacía nueva (primera fuente)."""
    path = _manifest_path()
    if not path.exists():
        return {"version": "1.0", "sources": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ManifestError(f"El manifiesto en {path} es ilegible o no es JSON válido: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("sources"), list):
        raise ManifestError(f"El manifiesto en {path} tiene un formato inválido.")
    return raw


def save_manifest(data: dict) -> None:
    """Escritura atómica (sección 20): nunca por concatenación de strings,
    nunca dejando un JSON truncado si el proceso falla a la mitad. Escribe a
    un archivo temporal en el MISMO directorio y hace `os.replace` (atómico
    en el mismo filesystem)."""
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def add_source_entry(entry: dict) -> None:
    """Agrega una fuente nueva al manifiesto (sección 6, paso 6). `entry` debe
    traer al menos los REQUIRED_SOURCE_FIELDS; se guarda tal cual (mismas
    claves que produce el flujo de alta), nunca se infiere nada aquí."""
    with _manifest_lock:
        raw = _read_raw()
        if any(str(source.get("id")) == entry["id"] for source in raw["sources"] if isinstance(source, dict)):
            raise ManifestError(f"Ya existe una entrada de manifiesto con id '{entry['id']}'.")
        raw["sources"].append(entry)
        save_manifest(raw)


def remove_source_entry(manifest_source_id: str) -> None:
    """Quita por completo una entrada (usada solo para rollback de una carga
    que falló antes de quedar realmente disponible: nunca existió como fuente
    viva, así que no hay nada que conservar como histórico)."""
    with _manifest_lock:
        raw = _read_raw()
        remaining = [s for s in raw["sources"] if not (isinstance(s, dict) and str(s.get("id")) == manifest_source_id)]
        if len(remaining) == len(raw["sources"]):
            return
        raw["sources"] = remaining
        save_manifest(raw)


def deactivate_source_entry(manifest_source_id: str) -> None:
    """Sección 18/19: eliminar una fuente con historial real nunca borra su
    entrada del manifiesto -solo la marca inactiva-, para que quede constancia
    de qué documento existió y se dejó de usar. El archivo físico y los
    chunks de Qdrant se eliminan aparte; esto solo actualiza el manifiesto."""
    with _manifest_lock:
        raw = _read_raw()
        found = False
        for source in raw["sources"]:
            if isinstance(source, dict) and str(source.get("id")) == manifest_source_id:
                source["active"] = False
                found = True
        if found:
            save_manifest(raw)


def next_manifest_source_id(base_slug: str) -> str:
    """Genera un id de manifiesto único (sección 6, paso 3) a partir de un
    slug base, agregando un sufijo corto si ya existe (colisión de nombre)."""
    import uuid
    with _manifest_lock:
        raw = _read_raw()
        existing_ids = {str(s.get("id")) for s in raw["sources"] if isinstance(s, dict)}
    candidate = base_slug
    if candidate not in existing_ids:
        return candidate
    return f"{base_slug}-{uuid.uuid4().hex[:6]}"
