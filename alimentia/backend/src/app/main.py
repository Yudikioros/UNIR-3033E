import json
import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from app.schemas.patient import PatientIn
from app.services.calculator import get_nutritional_baseline
from app.services.llm_client import generate_diet_plan_draft
from app.services.food_db import get_exact_macros
from app.services.rag_engine import build_knowledge_base

# --- GESTOR DE ARRANQUE EN SEGUNDO PLANO ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("⏳ Iniciando motor RAG en segundo plano...")
    threading.Thread(target=build_knowledge_base).start()
    yield

app = FastAPI(title="AlimentIA Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://172.18.0.5:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
embed_model = HuggingFaceEmbedding(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# --- CONEXIÓN SEGURA PEREZOSA (LAZY LOADING) ---


def get_clinical_retriever():
    """Se conecta a Qdrant solo cuando se necesita, evitando chocar con la ingesta."""
    try:
        client_qdrant = QdrantClient(url=QDRANT_URL)
        vector_store = QdrantVectorStore(
            client=client_qdrant, collection_name="medical_guidelines")
        index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store, embed_model=embed_model)
        return index.as_retriever(similarity_top_k=2)
    except Exception as e:
        print(f"Aviso: Qdrant no listo. {e}")
        return None


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AlimentIA Backend"}


@app.post("/api/v1/ingest-pdfs")
def ingest_pdfs():
    try:
        build_knowledge_base()
        return {"message": "✅ PDFs vectorizados y guardados en Qdrant exitosamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/generate-draft")
async def generate_draft(patient: PatientIn):
    try:
        nutritional_requirements = get_nutritional_baseline(
            weight=patient.weight, height=patient.height, age=patient.age,
            gender=patient.gender, activity_level=patient.activity_level
        )

        # 1. RAG Tabular (Excel INSP)
        exact_foods_context = []
        if patient.food_preferences:
            for food in patient.food_preferences:
                macros = get_exact_macros(food, limit=2)
                exact_foods_context.extend(macros)

        # 2. RAG Semántico (Guías Clínicas Qdrant)
        clinical_guidelines = ""
        retriever = get_clinical_retriever()  # <-- AHORA SÍ, SE CONECTA DE FORMA SEGURA
        if retriever:
            try:
                query = f"Recomendaciones nutricionales para {patient.goal} y patologías: {', '.join(patient.pathologies)}"
                nodes = retriever.retrieve(query)
                clinical_guidelines = "\n".join([n.node.text for n in nodes])
            except Exception as e:
                print(f"Aviso: Fallo al consultar Qdrant. {e}")

        # 3. Enviar todo al LLM
        llm_response_string = await generate_diet_plan_draft(
            patient, nutritional_requirements, exact_foods_context, clinical_guidelines
        )

        try:
            diet_plan_json = json.loads(llm_response_string)
        except json.JSONDecodeError as e:
            return {
                "message": f"Error parsing JSON from LLM: {str(e)}",
                "raw_llm_output": llm_response_string
            }

        return {
            "message": "Draft generated successfully.",
            "calculated_requirements": nutritional_requirements,
            "diet_plan": diet_plan_json
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
