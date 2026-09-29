import unittest
from types import SimpleNamespace

from pydantic import BaseModel

from app.services.llm_client import LLMClient, LLM_CONTEXT_TOKENS, _supported_reasoning_effort


class ReasoningEffortTests(unittest.TestCase):
    def test_uses_declared_named_effort(self):
        self.assertEqual(
            _supported_reasoning_effort('low', ['low', 'medium', 'high']), 'low')

    def test_omits_unsupported_effort(self):
        self.assertIsNone(_supported_reasoning_effort('low', [False]))

    def test_none_requires_explicit_disable_support(self):
        self.assertEqual(_supported_reasoning_effort(
            'none', [True, False]), 'none')
        self.assertIsNone(_supported_reasoning_effort('none', ['low', 'high']))


class _Response(BaseModel):
    value: str


class ContextWindowTests(unittest.IsolatedAsyncioTestCase):
    async def test_generation_uses_num_ctx_without_output_limit(self):
        captured = {}

        async def create(**options):
            captured.update(options)
            message = SimpleNamespace(content='{"value": "ok"}')
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=message, finish_reason='stop')],
                usage=None,
            )

        client = LLMClient(
            base_url='http://ollama:11434/v1', model='test-model')
        client._client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

        result, _ = await client.generate_structured(
            system_prompt='system', user_prompt='user', response_model=_Response)

        self.assertEqual(result.value, 'ok')
        self.assertNotIn('max_tokens', captured)
        self.assertEqual(captured['extra_body']
                         ['options']['num_ctx'], LLM_CONTEXT_TOKENS)


if __name__ == '__main__':
    unittest.main()
