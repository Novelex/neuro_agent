"""
LLM client factory.

Returns the correct BaseLLMClient implementation based on LLM_PROVIDER env var.
Default is always 'mock' — the service runs with no API keys out of the box.
"""

from app.llm.base import BaseLLMClient
from app.llm.mock_client import MockLLMClient
from app.core.llm_config import get_llm_settings


def get_llm_client() -> BaseLLMClient:
    """
    FastAPI-compatible factory (usable as a Depends() or called directly).

    LLM_PROVIDER=mock       → MockLLMClient (default, no API key needed)
    LLM_PROVIDER=openrouter → OpenRouterClient (requires OPENROUTER_API_KEY)
    """
    from app.llm.base import LLMError
    settings = get_llm_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "openrouter":
        if not settings.openrouter_api_key or not settings.openrouter_api_key.strip():
            raise LLMError(
                "OpenRouter API key is missing. "
                "Please set OPENROUTER_API_KEY in your environment/.env file."
            )
        model_name = settings.llm_model or settings.openrouter_model or "auto"
        from app.llm.openrouter_client import OpenRouterClient
        return OpenRouterClient(
            api_key=settings.openrouter_api_key,
            model=model_name,
            timeout=settings.llm_timeout_seconds,
        )

    # Default — always safe to run
    return MockLLMClient()

