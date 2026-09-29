import asyncio
import os
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prisma import Prisma
from app.repositories.legacy import list_plans, save_legacy_draft
from app.repositories.knowledge import sync_knowledge_sources
from app.routes.capture import router as capture_router
from app.routes.resources import router as resources_router
from app.routes.knowledge import router as knowledge_router
from app.routes.plans import router as plans_router
from app.routes.assistant import router as assistant_router
from app.routes.dashboard import router as dashboard_router

from app.schemas.patient import PatientIn
from app.schemas.plan import DietPlanDraft
from app.services.calculator import get_nutritional_baseline
from app.services.llm_client import generate_diet_plan_draft
from app.services.food_db import get_exact_macros
from app.services.rag_engine import (
    build_knowledge_base, KNOWLEDGE_COLLECTION, knowledge_path, get_embedding_model,
)
from app.services.ollama_runtime import preload_ollama_model

db = Prisma()

# Carga los recursos externos sin retrasar el inicio de la API.


async def _warm_up_runtime() -> None:
    try:
        await asyncio.to_thread(get_embedding_model)
        print("Modelo de embeddings RAG listo y reutilizable.")
    except Exception as exc:
        print(
            f"Aviso: no fue posible precargar el modelo de embeddings. {exc}")

    await preload_ollama_model()
    print("Iniciando motor RAG en segundo plano...")
    await asyncio.to_thread(build_knowledge_base)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🗄️ Conectando a la base de datos con Prisma...")
    await db.connect()

    try:
        await sync_knowledge_sources(db, knowledge_path())
    except Exception as exc:
        print(
            f"Aviso: no fue posible sincronizar fuentes de conocimiento. {exc}")

    warmup_task = asyncio.create_task(_warm_up_runtime())
    try:
        yield
    finally:
        warmup_task.cancel()
        with suppress(asyncio.CancelledError):
            await warmup_task
        await db.disconnect()

app = FastAPI(title="AlimentIA Backend", lifespan=lifespan)
app.state.db = db
app.include_router(capture_router)
app.include_router(resources_router)
app.include_router(knowledge_router)
app.include_router(plans_router)
app.include_router(assistant_router)
app.include_router(dashboard_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")


def get_clinical_retriever():
    """Conecta con Qdrant bajo demanda para la ruta de generación legacy."""
    try:
        from qdrant_client import QdrantClient
        from llama_index.vector_stores.qdrant import QdrantVectorStore
        from llama_index.core import VectorStoreIndex

        client_qdrant = QdrantClient(url=QDRANT_URL)
        vector_store = QdrantVectorStore(
            client=client_qdrant, collection_name=KNOWLEDGE_COLLECTION)
        index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store, embed_model=get_embedding_model())
        return index.as_retriever(similarity_top_k=2)
    except Exception as e:
        print(f"Aviso: Qdrant no listo. {e}")
        return None


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AlimentIA Backend"}


@app.post("/api/v1/generate-draft")
async def generate_draft(patient: PatientIn):
    try:
        nutritional_requirements = get_nutritional_baseline(
            weight=patient.weight, height=patient.height, age=patient.age,
            gender=patient.gender, activity_level=patient.activity_level
        )

        exact_foods_context = []
        if patient.food_preferences:
            for food in patient.food_preferences:
                macros = get_exact_macros(food, limit=2)
                exact_foods_context.extend(macros)

        clinical_guidelines = ""
        retriever = get_clinical_retriever()
        if retriever:
            try:
                query = f"Recomendaciones nutricionales para {patient.goal} y patologías: {', '.join(patient.pathologies)}"
                nodes = retriever.retrieve(query)
                clinical_guidelines = "\n".join([n.node.text for n in nodes])
            except Exception as e:
                print(f"Aviso: Fallo al consultar Qdrant. {e}")

        llm_response_string = await generate_diet_plan_draft(
            patient, nutritional_requirements, exact_foods_context, clinical_guidelines
        )

        try:
            validated_plan = DietPlanDraft.model_validate_json(
                llm_response_string)

            diet_plan_dict = validated_plan.model_dump()

        except Exception as e:
            return {
                "message": f"Fallo en la validación estructural del LLM: {str(e)}",
                "raw_llm_output": llm_response_string
            }

        nuevo_paciente = await save_legacy_draft(db, patient, nutritional_requirements, validated_plan)

        return {
            "message": "Draft generated successfully.",
            "patient_db_id": nuevo_paciente.id,
            "plan_db_id": nuevo_paciente.plans[0].id,
            "calculated_requirements": nutritional_requirements,
            "diet_plan": diet_plan_dict
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/plans")
async def get_plans():
    try:
        return await list_plans(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
