"""
OpenRouter LLM client.

Uses the OpenAI SDK pointed at OpenRouter's API gateway.
Supports 200+ models via a single API key.

Only used when LLM_PROVIDER=openrouter and OPENROUTER_API_KEY is set.
Requires: pip install openai (already in requirements.txt)
"""

import json
from app.llm.base import BaseLLMClient, LLMError


class OpenRouterClient(BaseLLMClient):

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

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
            raise LLMError(
                "OpenRouter API key is missing. "
                "Please set OPENROUTER_API_KEY in your environment/.env file."
            )

        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError:
            raise LLMError(
                "openai package is not installed. "
                "Run: pip install openai"
            )

        # Point the OpenAI SDK at OpenRouter's endpoint
        client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self.OPENROUTER_BASE_URL,
            timeout=self._timeout,
        )

        import time
        # Append a unique suffix to system prompt to guarantee a unique prompt hash (bypassing all caches)
        unique_system_prompt = system_prompt + f"\n\n(System metadata tag to ensure request uniqueness: {time.time_ns()})"

        try:
            response = await client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": unique_system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                extra_headers={
                    "HTTP-Referer": "https://neurosentio.app",
                    "X-Title": "NeuroSentio Copilot Agent",
                    "X-OpenRouter-Cache": "false",
                },
            )
            raw = response.choices[0].message.content or "{}"
            
            # Clean up markdown code blocks if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                # Find the first newline to strip ```json or ```
                first_nl = cleaned.find("\n")
                if first_nl != -1:
                    cleaned = cleaned[first_nl:].strip()
                else:
                    cleaned = cleaned[3:].strip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()
            
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMError(f"OpenRouter returned invalid JSON (raw: {repr(raw)}): {exc}") from exc
        except Exception as exc:
            raise LLMError(f"OpenRouter call failed: {exc}") from exc
