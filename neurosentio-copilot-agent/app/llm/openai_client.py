"""
OpenAI LLM client (optional).

Only used when LLM_PROVIDER=openai and OPENAI_API_KEY is set.
Install: pip install openai
"""

import json
from typing import Optional
from app.llm.base import BaseLLMClient, LLMError


class OpenAIClient(BaseLLMClient):

    _client: Optional[object] = None

    def __init__(self, api_key: str, model: str, timeout: int = 30):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def _get_client(self):
        """Lazily create and reuse the AsyncOpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI  # type: ignore
            self._client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout)
        return self._client

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str = "",
    ) -> dict:
        if not self._api_key or not self._api_key.strip():
            raise LLMError("OpenAI API key is missing. Please set OPENAI_API_KEY in your environment/.env file.")

        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError:
            raise LLMError(
                "openai package is not installed. "
                "Run: pip install openai"
            )

        client = self._get_client()

        try:
            response = await client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw = response.choices[0].message.content or "{}"
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMError(f"OpenAI returned invalid JSON: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"OpenAI call failed: {exc}") from exc

