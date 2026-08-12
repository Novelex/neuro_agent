"""
OpenRouter LLM client.

Uses the OpenAI SDK pointed at OpenRouter's API gateway.
Supports 200+ models via a single API key.

Only used when LLM_PROVIDER=openrouter and OPENROUTER_API_KEY is set.
Requires: pip install openai (already in requirements.txt)
"""

import json
import asyncio
import time
import logging
from typing import Optional
from app.llm.base import BaseLLMClient, LLMError

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Async-safe Token Bucket rate limiter for client-side API throttling."""

    def __init__(self, rate: float, capacity: float):
        self.rate = rate          # tokens per second
        self.capacity = capacity  # max tokens
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock: Optional[asyncio.Lock] = None  # Lazily created for event-loop safety

    def _get_lock(self) -> asyncio.Lock:
        """Lazily create the lock on the current event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def acquire(self):
        async with self._get_lock():
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
                self.last_update = time.monotonic()
            else:
                self.tokens -= 1.0


class OpenRouterClient(BaseLLMClient):

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    # Static fields for cheapest model cache (shared across all client instances)
    _cached_cheapest_model: Optional[str] = None
    _cache_time: float = 0.0

    # Static rate limiter: limit requests to ~20 requests per minute to avoid 429 errors
    _rate_limiter = TokenBucketRateLimiter(rate=0.33, capacity=5.0)

    # Reusable client instance (created once per OpenRouterClient instance)
    _openai_client: Optional[object] = None

    def __init__(self, api_key: str, model: str, timeout: int = 30):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def _get_openai_client(self):
        """Lazily create and reuse the AsyncOpenAI client."""
        if self._openai_client is None:
            from openai import AsyncOpenAI  # type: ignore
            self._openai_client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self.OPENROUTER_BASE_URL,
                timeout=self._timeout,
            )
        return self._openai_client

    async def _get_model_id(self) -> str:
        """Resolve model ID, falling back to openrouter/free if not specified."""
        if self._model and self._model != "auto":
            return self._model
        return "openrouter/free"

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

        # Ensure rate limiter acquires a token (client-side throttling)
        await self._rate_limiter.acquire()

        # Resolve model ID dynamically
        model_to_use = await self._get_model_id()

        # Reuse the AsyncOpenAI client (avoids connection churn)
        client = self._get_openai_client()

        try:
            response = await client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                extra_headers={
                    "HTTP-Referer": "https://neurosentio.app",
                    "X-Title": "NeuroSentio Copilot Agent",
                },
            )
            raw = response.choices[0].message.content or "{}"
            
            # Clean up markdown code blocks and conversational wrapper noise
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
            
            cleaned = cleaned.strip()

            # Locate the absolute boundaries of the JSON payload
            first_brace = cleaned.find("{")
            first_bracket = cleaned.find("[")
            
            start_idx = -1
            end_char = ""
            if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
                start_idx = first_brace
                end_char = "}"
            elif first_bracket != -1:
                start_idx = first_bracket
                end_char = "]"
                
            if start_idx != -1:
                end_idx = cleaned.rfind(end_char)
                if end_idx != -1 and end_idx > start_idx:
                    cleaned = cleaned[start_idx:end_idx + 1]

            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMError(f"OpenRouter returned invalid JSON (raw: {repr(raw)}): {exc}") from exc
        except Exception as exc:
            raise LLMError(f"OpenRouter call failed: {exc}") from exc
