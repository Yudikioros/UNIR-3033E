"""Arranque y calentamiento opcional del modelo Ollama local."""
import logging
import os

import httpx

logger = logging.getLogger("uvicorn.error")


async def preload_ollama_model() -> None:
    """Descarga (si hace falta) y deja cargado el modelo antes de servir API.

    Es una operación de mejor esfuerzo: un Ollama inaccesible no impide que
    FastAPI arranque. Los despliegues con un proveedor remoto se omiten.
    """
    if os.getenv("ALIMENTIA_OLLAMA_PRELOAD", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return

    base_url = os.getenv("LLM_API_URL", "http://ollama:11434/v1").rstrip("/")
    if "/v1" in base_url:
        base_url = base_url.rsplit("/v1", 1)[0]
    if "ollama" not in base_url.lower() and ":11434" not in base_url:
        logger.info("Precarga Ollama omitida: LLM_API_URL no apunta a Ollama.")
        return

    model = os.getenv("LLM_MODEL", "llama3.2:3b")
    logger.info("Preparando modelo Ollama '%s'; el primer arranque puede descargarlo.", model)
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=None) as client:
            pull = await client.post("/api/pull", json={"name": model, "stream": False})
            pull.raise_for_status()
            warmup = await client.post("/api/generate", json={
                "model": model,
                "prompt": "",
                "stream": False,
                "keep_alive": -1,
                "options": {"num_predict": 1},
            })
            warmup.raise_for_status()
        logger.info("Modelo Ollama '%s' listo y residente en memoria.", model)
    except Exception as exc:
        logger.warning("No fue posible precargar Ollama ('%s'); la API arrancará igualmente: %s", model, exc)
