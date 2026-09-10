"""Sincronización, lectura y administración de fuentes de conocimiento
(Fase 3.5; administración de documentos en la corrección de UX).

Nunca da de alta una fuente que no esté declarada en el manifiesto (ver
`app.services.knowledge_manifest`); nunca inventa procedencia.
"""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.knowledge import IndexStatus, KnowledgeSourceRead
from app.services import knowledge_manifest


class KnowledgeSourceNotFound(Exception):
    pass


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _checksum(path: Path) -> str:
    return checksum_bytes(path.read_bytes())


async def sync_knowledge_sources(db, knowledge_dir: Path) -> list:
    """Da de alta o actualiza en KnowledgeSource cada fuente autorizada presente en disco.

    Solo procesa lo que `authorized_documents` considera autorizado (declarado
    en el manifiesto Y presente en `knowledge_dir`). No elimina fuentes que
    dejen de estar en el manifiesto: se desactivan explícitamente aparte, no
    de forma silenciosa en cada arranque.

    También rellena `manifestSourceId`/`storedFilename`/`indexStatus` en
    filas legadas creadas antes de que existieran esas columnas (backfill
    natural: no hace falta un script de migración de datos aparte).
    """
    authorized = knowledge_manifest.authorized_documents(knowledge_dir)
    synced = []
    for source in authorized:
        publication_year = source.get('publicationYear')
        data = {
            'documentName': source['name'], 'institution': source.get('institution'),
            'version': source.get('version'), 'sourceType': source.get('type'),
            'originalFilename': source['file'], 'checksum': _checksum(source['path']),
            'isActive': True, 'manifestSourceId': source['id'], 'storedFilename': source['file'],
            'publicationDate': datetime(publication_year, 1, 1, tzinfo=timezone.utc) if publication_year else None,
        }
        existing = await db.knowledgesource.find_first(where={'originalFilename': source['file']})
        if existing:
            if existing.indexStatus != IndexStatus.INDEXED.value:
                data['indexStatus'] = IndexStatus.INDEXED.value
            record = await db.knowledgesource.update(where={'id': existing.id}, data=data)
        else:
            record = await db.knowledgesource.create(data={**data, 'indexStatus': IndexStatus.INDEXED.value})
        synced.append(record)
    return synced


async def resolve_source_id(db, manifest_source_id: str) -> str | None:
    """Resuelve el slug de una fuente en el manifiesto (el `sourceId` grabado en
    los metadatos de un chunk del RAG) al UUID real de `KnowledgeSource`.

    Devuelve `None` si el slug no existe en el manifiesto actual, o si existe
    pero todavía no fue sincronizado a base de datos (por ejemplo, el archivo
    aún no está presente en disco). Nunca inventa ni adivina un id: la
    ausencia de correspondencia se trata como "fuente no disponible", no como
    error.
    """
    row = await db.knowledgesource.find_first(where={'manifestSourceId': manifest_source_id})
    if row:
        return row.id
    manifest = knowledge_manifest.load_manifest()
    entry = next((source for source in manifest['sources'] if source['id'] == manifest_source_id), None)
    if entry is None:
        return None
    row = await db.knowledgesource.find_first(where={'originalFilename': entry['file']})
    return row.id if row else None


def _source_read(row) -> KnowledgeSourceRead:
    data = {k: v for k, v in row.model_dump().items() if k in KnowledgeSourceRead.model_fields}
    return KnowledgeSourceRead.model_validate(data)


async def list_sources(db, *, include_inactive: bool = True) -> list[KnowledgeSourceRead]:
    """Por defecto incluye fuentes inactivas (comportamiento histórico, del
    que depende p.ej. el asistente para poder mostrar fuentes "históricas").
    La ruta HTTP de administración pasa `include_inactive=False` para que
    `/sources` muestre solo la biblioteca activa por defecto (sección 18)."""
    where = None if include_inactive else {'isActive': True}
    rows = await db.knowledgesource.find_many(where=where, order={'createdAt': 'desc'})
    return [_source_read(row) for row in rows]


async def get_source(db, source_id: str) -> KnowledgeSourceRead:
    row = await db.knowledgesource.find_unique(where={'id': source_id})
    if row is None:
        raise KnowledgeSourceNotFound(source_id)
    return _source_read(row)


async def get_source_row(db, source_id: str):
    """Variante que devuelve la fila real de Prisma (no el DTO), para las
    rutas de administración que necesitan campos internos (`storedFilename`,
    `manifestSourceId`) que nunca se exponen al frontend."""
    row = await db.knowledgesource.find_unique(where={'id': source_id})
    if row is None:
        raise KnowledgeSourceNotFound(source_id)
    return row


async def find_active_by_checksum(db, checksum: str):
    return await db.knowledgesource.find_first(where={'checksum': checksum, 'isActive': True})


async def has_history(db, source_id: str) -> bool:
    """Sección 18: una fuente con planes históricos que la citaron nunca debe
    borrarse físicamente -la FK `RetrievedSource.knowledgeSourceId` ya lo
    impide a nivel de base de datos (`onDelete: Restrict`), pero se verifica
    aquí explícitamente para decidir el flujo (desactivar vs. borrar)."""
    count = await db.retrievedsource.count(where={'knowledgeSourceId': source_id})
    return count > 0


async def create_pending_source(db, *, manifest_source_id: str, document_name: str, institution: str | None,
                                 version: str | None, source_type: str, publication_date, original_filename: str,
                                 stored_filename: str, checksum: str):
    return await db.knowledgesource.create(data={
        'documentName': document_name, 'institution': institution, 'version': version,
        'sourceType': source_type, 'publicationDate': publication_date,
        'originalFilename': original_filename, 'storedFilename': stored_filename, 'checksum': checksum,
        'manifestSourceId': manifest_source_id, 'isActive': True, 'indexStatus': IndexStatus.INDEXING.value,
    })


async def mark_indexed(db, source_id: str):
    return await db.knowledgesource.update(
        where={'id': source_id}, data={'indexStatus': IndexStatus.INDEXED.value, 'indexError': None})


async def mark_index_error(db, source_id: str, message: str):
    return await db.knowledgesource.update(
        where={'id': source_id}, data={'indexStatus': IndexStatus.ERROR.value, 'indexError': message[:2000]})


async def deactivate_source(db, source_id: str):
    return await db.knowledgesource.update(where={'id': source_id}, data={
        'isActive': False, 'storedFilename': None,
    })


async def knowledge_base_status_db(db) -> dict:
    """Sección 32: `indexedDocumentCount` refleja el estado REAL en base de
    datos (fuentes activas cuyo `indexStatus` es INDEXED), no un conteo
    derivado únicamente de archivos en disco -que podía incluir una fuente
    cuya indexación falló-. Nunca cacheado: se consulta en cada llamada."""
    manifest = knowledge_manifest.load_manifest()
    indexed_count = await db.knowledgesource.count(where={'isActive': True, 'indexStatus': IndexStatus.INDEXED.value})
    return {
        'ready': indexed_count > 0,
        'documentCount': indexed_count,
        'pathConfigured': True,
        'knowledgeBaseVersion': manifest['version'],
        'authorizedSourceCount': len(manifest['sources']),
        'indexedDocumentCount': indexed_count,
    }


async def delete_source_row(db, source_id: str) -> None:
    """Borrado físico de la fila (sección 19): solo se llama cuando ya se
    verificó que no existe ningún `RetrievedSource` histórico apuntando a
    ella -si existiera, la FK `onDelete: Restrict` lo impediría de todas
    formas-."""
    await db.knowledgesource.delete(where={'id': source_id})
