"""
Anthropic LLM client (optional).

Only used when LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY is set.
Install: pip install anthropic
"""

import json
from app.llm.base import BaseLLMClient, LLMError


class AnthropicClient(BaseLLMClient):

    def __init__(self, api_key: str, model: str, timeout: int = 30):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str = "",
    ) -> dict:
        if not self._api_key or not self._api_key.strip():
            raise LLMError("Anthropic API key is missing. Please set ANTHROPIC_API_KEY in your environment/.env file.")

        try:
            import anthropic  # type: ignore
        except ImportError:
            raise LLMError(
                "anthropic package is not installed. "
                "Run: pip install anthropic"
            )

        # Use AsyncAnthropic to avoid blocking the event loop
        client = anthropic.AsyncAnthropic(api_key=self._api_key)

        try:
            message = await client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = message.content[0].text
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Anthropic returned invalid JSON: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"Anthropic call failed: {exc}") from exc

