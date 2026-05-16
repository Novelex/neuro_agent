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
    LLM_PROVIDER=anthropic  → AnthropicClient (requires ANTHROPIC_API_KEY)
    LLM_PROVIDER=openai     → OpenAIClient (requires OPENAI_API_KEY)
    """
    settings = get_llm_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "anthropic":
        # Lazy import so tests don't require the anthropic package
        from app.llm.anthropic_client import AnthropicClient
        return AnthropicClient(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model or "claude-3-5-haiku-20241022",
            timeout=settings.llm_timeout_seconds,
        )

    if provider == "openai":
        from app.llm.openai_client import OpenAIClient
        return OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.llm_model or "gpt-4o-mini",
            timeout=settings.llm_timeout_seconds,
        )

    # Default — always safe to run
    return MockLLMClient()
