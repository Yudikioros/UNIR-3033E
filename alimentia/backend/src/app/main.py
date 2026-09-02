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
from prisma import Prisma

from app.schemas.patient import PatientIn
from app.schemas.plan import DietPlanDraft
from app.services.calculator import get_nutritional_baseline
from app.services.llm_client import generate_diet_plan_draft
from app.services.food_db import get_exact_macros
from app.services.rag_engine import build_knowledge_base

# Instanciamos el cliente de Prisma
db = Prisma()

# --- GESTOR DE ARRANQUE EN SEGUNDO PLANO ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 2. CONEXIÓN A LA BASE DE DATOS
    print("🗄️ Conectando a la base de datos con Prisma...")
    await db.connect()

    print("⏳ Iniciando motor RAG en segundo plano...")
    threading.Thread(target=build_knowledge_base).start()
    yield

    # Desconexión segura al apagar
    await db.disconnect()

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
        retriever = get_clinical_retriever()
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

        # 4. VALIDACIÓN ESTRICTA CON PYDANTIC
        try:
            # Pydantic valida que la respuesta cumpla con la estructura exacta de DietPlanDraft
            validated_plan = DietPlanDraft.model_validate_json(
                llm_response_string)

            # Convertimos el modelo validado a un diccionario seguro para la respuesta
            diet_plan_dict = validated_plan.model_dump()

        except Exception as e:
            # Si el LLM no generó el JSON esperado, lo atrapamos aquí
            return {
                "message": f"Fallo en la validación estructural del LLM: {str(e)}",
                "raw_llm_output": llm_response_string
            }

        # 5. GUARDADO EN BASE DE DATOS CON PRISMA
        nuevo_paciente = await db.patient.create(
            data={
                "age": patient.age,
                "gender": patient.gender,
                "goal": patient.goal,
                "pathologies": ", ".join(patient.pathologies),
                "plans": {
                    "create": [{
                        "tdee_calculated": nutritional_requirements["tdee_kcal"],
                        # model_dump_json() asegura que guardamos texto 100% válido en la base de datos
                        "plan_json": validated_plan.model_dump_json(),
                        "status": "BORRADOR"
                    }]
                }
            },
            include={"plans": True}
        )

        return {
            "message": "Draft generated successfully.",
            "patient_db_id": nuevo_paciente.id,
            "plan_db_id": nuevo_paciente.plans[0].id,
            "calculated_requirements": nutritional_requirements,
            "diet_plan": diet_plan_dict
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/patients")
async def get_patients():
    try:
        # Obtenemos todos los pacientes e incluimos sus planes para saber el estado
        patients = await db.patient.find_many(
            include={"plans": True},
            order={"createdAt": "desc"}
        )
        return patients
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/plans")
async def get_plans():
    try:
        # Obtenemos todos los planes e incluimos los datos del paciente asociado
        plans = await db.dietplan.find_many(
            include={"patient": True},
            order={"createdAt": "desc"}
        )
        return plans
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
