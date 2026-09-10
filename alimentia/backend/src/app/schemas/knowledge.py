"""Contratos de fuentes de conocimiento (Fase 3.5; administración de
documentos en la corrección de UX)."""
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.persistence import Contract


class IndexStatus(StrEnum):
    """Estado real de indexación en Qdrant (sección 10): nunca se muestra
    "Vigente" solo porque existe la fila en KnowledgeSource."""
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    ERROR = "ERROR"


class KnowledgeSourceRead(Contract):
    id: str
    documentName: str
    institution: str | None = None
    version: str | None = None
    publicationDate: datetime | None = None
    sourceType: str | None = None
    isActive: bool
    originalFilename: str | None = None
    checksum: str | None = None
    createdAt: datetime
    updatedAt: datetime
    manifestSourceId: str | None = None
    indexStatus: str = IndexStatus.INDEXED.value
    indexError: str | None = None


class KnowledgeSourceCreateForm(Contract):
    """Metadata del formulario multipart de alta (sección 5/23). El archivo en
    sí llega como `UploadFile`, fuera de este contrato. Nunca se infiere
    institución/versión/fecha mediante LLM: son siempre datos del usuario."""
    name: str = Field(min_length=1, max_length=300)
    institution: str | None = Field(default=None, max_length=300)
    version: str | None = Field(default=None, max_length=100)
    sourceType: str = Field(min_length=1)
    publicationDate: str | None = None
