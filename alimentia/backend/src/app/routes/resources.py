"""Rutas de estado e ingesta de recursos externos (PDFs y BAM.xlsx).

Aisladas del arranque LLM/RAG completo, igual que capture.py, para poder
probarse sin depender de Qdrant/Ollama en ejecución.
"""
from fastapi import APIRouter, HTTPException, Request
from app.repositories.knowledge import knowledge_base_status_db
from app.services.food_db import food_database_status
from app.services.llm_client import llm_status
from app.services.nutrition_rules import NUTRITION_RULESET_VERSION
from app.services.rag_engine import build_knowledge_base

router = APIRouter(prefix='/api/v1')

_INGEST_MESSAGES = {
    'no_documents': 'Todavía no hay documentos disponibles para la base de conocimiento clínico.',
    'already_ready': 'La base de conocimiento clínico ya estaba lista.',
    'error': 'No fue posible completar la ingesta de documentos.',
    'ingested': 'PDFs vectorizados y guardados en Qdrant exitosamente.',
}


@router.get('/resources/status')
async def resources_status(request: Request):
    return {
        # Administración de documentos (sección 32): refleja el estado real
        # en base de datos (KnowledgeSource.indexStatus), nunca un valor
        # cacheado ni derivado solo de archivos en disco.
        'knowledgeBase': await knowledge_base_status_db(request.app.state.db),
        'foodDatabase': food_database_status(),
        # Fase 6, sección 36: nunca llama al motor/LLM para determinar el estado.
        'calculationEngine': {'ready': True, 'rulesetVersion': NUTRITION_RULESET_VERSION},
        'llm': llm_status(),
    }


@router.post('/ingest-pdfs')
def ingest_pdfs():
    try:
        result = build_knowledge_base(wait_for_qdrant=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        'message': _INGEST_MESSAGES[result['status']],
        'documentCount': result.get('documentCount', 0),
    }
