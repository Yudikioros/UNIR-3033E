"""
Rutas de fuentes de conocimiento (Fase 3.5) y de administración de
documentos (alta, eliminación, visualización, descarga, reintento de
indexación).

El frontend nunca envía ni recibe una ruta física (sección 14): solo
`source_id`. `knowledge_storage.resolve_stored_path` es el único punto que
traduce eso a un archivo real, siempre verificado dentro del directorio
autorizado.
"""
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.repositories.knowledge import KnowledgeSourceNotFound, get_source, get_source_row, list_sources
from app.services import knowledge_admin, knowledge_storage
from app.services.knowledge_admin import KnowledgeAdminError

router = APIRouter(prefix='/api/v1')


def _raise(exc: KnowledgeAdminError):
    raise HTTPException(status_code=exc.status, detail=exc.message) from None


@router.get('/sources')
async def sources(request: Request, includeInactive: bool = False):
    return await list_sources(request.app.state.db, include_inactive=includeInactive)


@router.get('/sources/{source_id}')
async def source(source_id: str, request: Request):
    try:
        return await get_source(request.app.state.db, source_id)
    except KnowledgeSourceNotFound:
        raise HTTPException(status_code=404, detail='No se encontró la fuente de conocimiento.')


@router.post('/sources', status_code=201)
async def create_source(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    institution: str | None = Form(None),
    version: str | None = Form(None),
    sourceType: str = Form(...),
    publicationDate: str | None = Form(None),
):
    data = await file.read()
    try:
        return await knowledge_admin.add_source(
            request.app.state.db, file_bytes=data, upload_filename=file.filename or '',
            content_type=file.content_type, name=name, institution=institution, version=version,
            source_type=sourceType, publication_date=publicationDate)
    except KnowledgeAdminError as exc:
        _raise(exc)


@router.post('/sources/{source_id}/reindex')
async def reindex_source(source_id: str, request: Request):
    try:
        return await knowledge_admin.reindex_source(request.app.state.db, source_id)
    except KnowledgeAdminError as exc:
        _raise(exc)


@router.delete('/sources/{source_id}', status_code=204)
async def delete_source(source_id: str, request: Request):
    try:
        await knowledge_admin.delete_source(request.app.state.db, source_id)
    except KnowledgeAdminError as exc:
        _raise(exc)


async def _resolve_document_path(request: Request, source_id: str):
    try:
        row = await get_source_row(request.app.state.db, source_id)
    except KnowledgeSourceNotFound:
        raise HTTPException(status_code=404, detail='No se encontró la fuente de conocimiento.')
    if not row.isActive or not row.storedFilename:
        raise HTTPException(status_code=404, detail='El documento de esta fuente ya no está disponible en la biblioteca.')
    try:
        path = knowledge_storage.resolve_stored_path(row.storedFilename)
    except knowledge_storage.FileValidationError:
        raise HTTPException(status_code=404, detail='El documento de esta fuente ya no está disponible.')
    if not path.exists():
        raise HTTPException(status_code=404, detail='El documento de esta fuente ya no está disponible.')
    display_name = knowledge_storage.sanitize_display_filename(row.originalFilename or path.name)
    return path, display_name


@router.get('/sources/{source_id}/document')
async def view_document(source_id: str, request: Request):
    path, display_name = await _resolve_document_path(request, source_id)
    return FileResponse(path, media_type='application/pdf', filename=display_name, content_disposition_type='inline')


@router.get('/sources/{source_id}/download')
async def download_document(source_id: str, request: Request):
    path, display_name = await _resolve_document_path(request, source_id)
    return FileResponse(path, media_type='application/pdf', filename=display_name, content_disposition_type='attachment')
