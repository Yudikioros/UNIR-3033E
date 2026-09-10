"""Pruebas HTTP de POST /api/v1/assistant/chat (sección 31)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from prisma import Prisma

from app.routes.assistant import router
from app.schemas.assistant import AssistantDecision
from test_assistant_service import ScriptedAssistantLLM
from test_persistence import apply_sql


class AssistantEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "assistant.db"
        apply_sql(self.path)
        self.db = Prisma(datasource={"url": "file:" + self.path.as_posix()})
        await self.db.connect()
        self.app = FastAPI()
        self.app.state.db = self.db
        self.app.include_router(router)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test/api/v1/")

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.db.disconnect()
        self.temp.cleanup()

    async def test_mensaje_vacio_devuelve_422(self):
        response = await self.client.post("assistant/chat", json={"message": ""})
        self.assertEqual(response.status_code, 422)

    async def test_respuesta_exitosa(self):
        llm = ScriptedAssistantLLM(decisions=[
            AssistantDecision(action="answer", answer="Hola, ¿en qué puedo ayudarte?"),
        ])
        with patch("app.services.assistant_service.LLMClient", return_value=llm):
            response = await self.client.post("assistant/chat", json={
                "message": "hola", "context": {"route": "/patients"}, "conversation": [],
            })
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["answer"], "Hola, ¿en qué puedo ayudarte?")
        self.assertEqual(body["toolsUsed"], [])
        self.assertEqual(body["sources"], [])
        self.assertEqual(body["metadata"]["promptVersion"], "1.0")
        self.assertIn("executionTimeMs", body["metadata"])

    async def test_contexto_por_defecto_si_se_omite(self):
        llm = ScriptedAssistantLLM(decisions=[AssistantDecision(action="answer", answer="ok")])
        with patch("app.services.assistant_service.LLMClient", return_value=llm):
            response = await self.client.post("assistant/chat", json={"message": "hola"})
        self.assertEqual(response.status_code, 200, response.text)


if __name__ == "__main__":
    unittest.main()
