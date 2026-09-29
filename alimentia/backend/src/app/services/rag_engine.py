import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

import pypdf
from pydantic import BaseModel
import qdrant_client
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.services import knowledge_manifest

logger = logging.getLogger("uvicorn.error")


class _PyPdfReader:
    """Extrae el texto de cada página PDF con `pypdf`."""

    def load_data(self, file, extra_info=None):
        from llama_index.core import Document

        reader = pypdf.PdfReader(str(file))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(
            page_text for page_text in pages if page_text.strip())
        if not text.strip():
            # Evita indexar documentos vacíos o sin texto utilizable.
            return []
        metadata = dict(extra_info or {})
        metadata.setdefault("file_name", Path(file).name)
        metadata.setdefault("file_path", str(file))
        return [Document(text=text, metadata=metadata)]


QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
KNOWLEDGE_COLLECTION = "alimentia_knowledge_v1"

# Filtra fuentes según el alcance declarado en el manifiesto.
ALLOWED_SCOPES = {"adult_general"}
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_embedding_model = None
_embedding_model_lock = threading.Lock()


def HuggingFaceEmbedding(*args, **kwargs):
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding as Embedding

    return Embedding(*args, **kwargs)


def _llama_index_components():
    from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
    from llama_index.vector_stores.qdrant import QdrantVectorStore

    return SimpleDirectoryReader, StorageContext, VectorStoreIndex, QdrantVectorStore


def get_embedding_model():
    """Carga el modelo de embeddings una sola vez y lo comparte en el proceso."""
    global _embedding_model
    if _embedding_model is None:
        with _embedding_model_lock:
            if _embedding_model is None:
                _embedding_model = HuggingFaceEmbedding(
                    model_name=EMBEDDING_MODEL_NAME)
    return _embedding_model


def knowledge_path() -> Path:
    return Path(os.getenv("ALIMENTIA_KNOWLEDGE_PATH", "/app/data/pdfs"))


def _ensure_knowledge_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def knowledge_base_status() -> dict:
    """Informa qué fuentes autorizadas están presentes, sin consultar Qdrant."""
    knowledge_dir = knowledge_path()
    manifest = knowledge_manifest.load_manifest()
    authorized = knowledge_manifest.authorized_documents(
        knowledge_dir) if knowledge_dir.exists() else []
    return {
        "ready": len(authorized) > 0,
        "documentCount": len(authorized),
        "pathConfigured": True,
        "knowledgeBaseVersion": manifest["version"],
        "authorizedSourceCount": len(manifest["sources"]),
        "indexedDocumentCount": len(authorized),
    }


def build_knowledge_base(wait_for_qdrant: bool = True) -> dict:
    """
    Ingiere únicamente los documentos autorizados por el manifiesto y los
    indexa en Qdrant. Un archivo presente en la carpeta que no esté declarado
    en el manifiesto se ignora por completo (nunca se lee).

    Es seguro llamarla sin manifiesto, con la carpeta ausente o sin
    documentos autorizados presentes: registra el estado correspondiente y
    termina sin lanzar excepciones.
    """
    if wait_for_qdrant:
        # Damos margen para asegurar que el contenedor de Qdrant ya encendió.
        time.sleep(5)

    knowledge_dir = _ensure_knowledge_dir(knowledge_path())
    SimpleDirectoryReader, StorageContext, VectorStoreIndex, QdrantVectorStore = _llama_index_components()

    authorized = knowledge_manifest.authorized_documents(knowledge_dir)
    if not authorized:
        logger.warning(
            "No hay documentos autorizados por el manifiesto disponibles en %s todavía. "
            "La base de conocimiento clínico queda pendiente de configuración.", knowledge_dir)
        return {"status": "no_documents", "documentCount": 0}

    try:
        documents = SimpleDirectoryReader(
            input_files=[str(source["path"]) for source in authorized],
            file_extractor={".pdf": _PyPdfReader()},
        ).load_data()
    except ValueError as exc:
        logger.warning(
            "No se encontraron documentos soportados entre los autorizados en %s: %s", knowledge_dir, exc)
        return {"status": "no_documents", "documentCount": 0}
    except Exception as exc:
        logger.error(
            "Error inesperado leyendo documentos autorizados de %s: %s", knowledge_dir, exc)
        return {"status": "error", "documentCount": 0}

    if not documents:
        logger.warning(
            "Ninguno de los documentos autorizados en %s resultó procesable todavía.", knowledge_dir)
        return {"status": "no_documents", "documentCount": 0}

    by_filename = {source["path"].name: source for source in authorized}
    for document in documents:
        file_name = Path(document.metadata.get("file_name")
                         or document.metadata.get("file_path", "")).name
        source = by_filename.get(file_name)
        if source:
            document.metadata.update(
                sourceId=source["id"], documentName=source["name"],
                institution=source.get("institution"), sourceVersion=source.get("version"),
                scope=list(source.get("scope") or []),
            )

    try:
        client = qdrant_client.QdrantClient(url=QDRANT_URL)

        try:
            collection_info = client.get_collection(KNOWLEDGE_COLLECTION)
            if collection_info.points_count > 0:
                logger.info(
                    "La base vectorial clínica ya está lista (%s puntos). "
                    "Se omite la ingesta automática.", collection_info.points_count)
                return {"status": "already_ready", "documentCount": collection_info.points_count}
        except Exception:
            logger.info(
                "Base vectorial clínica vacía o no inicializada. Se indexarán %s documento(s) autorizado(s).",
                len(documents))

        embed_model = get_embedding_model()
        vector_store = QdrantVectorStore(
            client=client, collection_name=KNOWLEDGE_COLLECTION)
        storage_context = StorageContext.from_defaults(
            vector_store=vector_store)

        VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            embed_model=embed_model,
            show_progress=True
        )
    except Exception as exc:
        logger.error(
            "Error inesperado indexando documentos en Qdrant: %s", exc)
        return {"status": "error", "documentCount": len(documents)}

    logger.info(
        "Ingesta de documentos finalizada. Base de conocimiento clínico lista con %s documento(s) autorizado(s).",
        len(documents))
    return {"status": "ingested", "documentCount": len(documents)}


def _source_filter(manifest_source_id: str) -> Filter:
    return Filter(must=[FieldCondition(key="sourceId", match=MatchValue(value=manifest_source_id))])


def count_source_chunks(manifest_source_id: str) -> int:
    """Verificación real (sección 6 paso 9 / sección 17) de cuántos puntos de
    Qdrant pertenecen a una fuente -consultando Qdrant directamente, nunca
    asumiendo que "se ejecutó sin excepción" equivale a "quedó indexado"-."""
    try:
        client = qdrant_client.QdrantClient(url=QDRANT_URL)
        if not client.collection_exists(KNOWLEDGE_COLLECTION):
            return 0
        result = client.count(KNOWLEDGE_COLLECTION, count_filter=_source_filter(
            manifest_source_id), exact=True)
        return result.count
    except Exception as exc:
        logger.warning(
            "No fue posible contar los chunks de '%s' en Qdrant: %s", manifest_source_id, exc)
        return 0


def index_source(source: dict) -> dict:
    """Indexa ÚNICAMENTE el documento de `source` (sección 9): nunca
    reconstruye toda la colección para dar de alta un documento nuevo.
    `source` debe tener la misma forma que produce
    `knowledge_manifest.authorized_documents()` para una fuente (incluye
    `path`, un `Path` real ya verificado). Devuelve
    `{"status": "indexed"|"no_content"|"error", "chunkCount": int, "message": str|None}`.
    """
    path = source["path"]
    SimpleDirectoryReader, StorageContext, VectorStoreIndex, QdrantVectorStore = _llama_index_components()
    try:
        documents = SimpleDirectoryReader(
            input_files=[str(path)], file_extractor={".pdf": _PyPdfReader()},
        ).load_data()
    except Exception as exc:
        logger.error(
            "Error leyendo el documento '%s' para indexar: %s", path, exc)
        return {"status": "error", "chunkCount": 0, "message": str(exc)}

    if not documents:
        return {"status": "no_content", "chunkCount": 0, "message": "El documento no produjo contenido extraíble."}

    for document in documents:
        document.metadata.update(
            sourceId=source["id"], documentName=source["name"],
            institution=source.get("institution"), sourceVersion=source.get("version"),
            scope=list(source.get("scope") or []),
        )

    try:
        embed_model = get_embedding_model()
        client = qdrant_client.QdrantClient(url=QDRANT_URL)
        vector_store = QdrantVectorStore(
            client=client, collection_name=KNOWLEDGE_COLLECTION)
        if client.collection_exists(KNOWLEDGE_COLLECTION):
            # Indexación incremental real: se adjunta al índice existente y
            # solo se insertan los nodos de ESTE documento -nunca se
            # reconstruye la colección completa por dar de alta una fuente-.
            index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store, embed_model=embed_model)
            for document in documents:
                index.insert(document)
        else:
            # Primer documento indexado en este despliegue: todavía no existe
            # una colección a la que "adjuntarse" (from_vector_store
            # necesita que ya exista). Se crea con este único documento -no
            # es una reconstrucción de nada preexistente, porque no había
            # nada preexistente-.
            storage_context = StorageContext.from_defaults(
                vector_store=vector_store)
            VectorStoreIndex.from_documents(
                documents, storage_context=storage_context, embed_model=embed_model)
    except Exception as exc:
        logger.error(
            "Error indexando el documento '%s' en Qdrant: %s", path, exc)
        return {"status": "error", "chunkCount": 0, "message": str(exc)}

    chunk_count = count_source_chunks(source["id"])
    if chunk_count == 0:
        return {"status": "no_content", "chunkCount": 0, "message": "El documento no generó fragmentos indexables."}
    return {"status": "indexed", "chunkCount": chunk_count, "message": None}


def delete_source_chunks(manifest_source_id: str) -> int:
    """Sección 17: elimina SOLO los puntos de Qdrant de esta fuente mediante
    un filtro por metadata (`sourceId`) -nunca borra ni reconstruye toda la
    colección-. Devuelve cuántos puntos tenía antes de borrar (0 si no había
    ninguno, o si la colección todavía no existe: eso no es un error, es
    "nada que limpiar"). Cualquier error real de comunicación con Qdrant se
    propaga -el llamador decide cómo reportarlo- en vez de fingir éxito."""
    client = qdrant_client.QdrantClient(url=QDRANT_URL)
    if not client.collection_exists(KNOWLEDGE_COLLECTION):
        return 0
    before = count_source_chunks(manifest_source_id)
    if before == 0:
        return 0
    client.delete(KNOWLEDGE_COLLECTION,
                  points_selector=_source_filter(manifest_source_id))
    return before


class RetrievedKnowledgeChunk(BaseModel):
    """Resultado de una búsqueda documental, siempre con procedencia verificable."""
    sourceId: str
    documentName: str
    institution: Optional[str] = None
    version: Optional[str] = None
    section: Optional[str] = None
    content: str
    score: Optional[float] = None


class KnowledgeBaseService:
    """
    Punto único de búsqueda documental para la futura generación (Fase 4).

    Regla crítica: nunca devuelve un fragmento sin `sourceId`/`documentName`
    verificables. Si Qdrant no está listo o no hay documentos indexados,
    devuelve una lista vacía en lugar de lanzar una excepción.
    """

    def __init__(self, collection_name: str = KNOWLEDGE_COLLECTION, qdrant_url: str = QDRANT_URL):
        self.collection_name = collection_name
        self.qdrant_url = qdrant_url
        self._cached_retriever = None
        self._retriever_lock = threading.Lock()

    def _retriever(self, embed_model):
        _, _, VectorStoreIndex, QdrantVectorStore = _llama_index_components()
        client = qdrant_client.QdrantClient(url=self.qdrant_url)
        vector_store = QdrantVectorStore(
            client=client, collection_name=self.collection_name)
        index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store, embed_model=embed_model)
        return index.as_retriever(similarity_top_k=5)

    def _get_retriever(self, embed_model):
        if self._cached_retriever is None:
            with self._retriever_lock:
                if self._cached_retriever is None:
                    self._cached_retriever = self._retriever(embed_model)
        return self._cached_retriever

    def search(self, query: str, top_k: int = 3) -> list[RetrievedKnowledgeChunk]:
        try:
            embed_model = get_embedding_model()
            retriever = self._get_retriever(embed_model)
            nodes = retriever.retrieve(query)
        except Exception as exc:
            logger.warning(
                "Búsqueda documental no disponible todavía: %s", exc)
            return []

        results = []
        for node in nodes[:top_k]:
            metadata = node.node.metadata or {}
            source_id = metadata.get("sourceId")
            document_name = metadata.get("documentName")
            if not source_id or not document_name:
                # Sin procedencia verificable no se expone: nunca se inventa una fuente.
                continue
            scope = metadata.get("scope") or []
            if scope and not (set(scope) & ALLOWED_SCOPES):
                # Documento fuera del alcance del MVP (p.ej. pediatría): no se
                # usa para un borrador general aunque haya sido recuperado.
                continue
            results.append(RetrievedKnowledgeChunk(
                sourceId=source_id, documentName=document_name,
                institution=metadata.get("institution"), version=metadata.get("sourceVersion"),
                section=metadata.get("section"), content=node.node.get_content(),
                score=node.score,
            ))
        return results


knowledge_base_service = KnowledgeBaseService()
