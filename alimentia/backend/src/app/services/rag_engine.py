import os
import time
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import qdrant_client

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
DATA_DIR = "/app/data/pdfs"


def build_knowledge_base():
    """
    Ingests PDF files and indexes them into Qdrant automatically on startup.
    """
    # Damos 5 segundos de gracia para asegurar que el contenedor de Qdrant ya encendió
    time.sleep(5)

    try:
        client = qdrant_client.QdrantClient(url=QDRANT_URL)

        # EL SEGURO: Verificamos si la colección ya existe y tiene datos
        collection_info = client.get_collection("medical_guidelines")
        if collection_info.points_count > 0:
            print(
                "✅ La base vectorial clínica ya está lista. Saltando ingesta automática.")
            return
    except Exception:
        print("⚙️ Base vectorial vacía. Iniciando lectura y vectorización de PDFs...")

    if not os.path.exists(DATA_DIR):
        print(f"Directorio no encontrado: {DATA_DIR}")
        return

    documents = SimpleDirectoryReader(DATA_DIR).load_data()
    if not documents:
        print("No hay documentos en la carpeta de PDFs.")
        return

    embed_model = HuggingFaceEmbedding(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    vector_store = QdrantVectorStore(
        client=client, collection_name="medical_guidelines")
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True
    )
    print("✅ Ingesta de PDFs finalizada. Base de conocimiento lista.")
    return index
