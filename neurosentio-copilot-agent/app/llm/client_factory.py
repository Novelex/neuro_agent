"""
LLM client factory.

Returns the correct BaseLLMClient implementation based on LLM_PROVIDER env var.
"""

from app.llm.base import BaseLLMClient
from app.core.llm_config import get_llm_settings

def get_llm_client() -> BaseLLMClient:
    """
    FastAPI-compatible factory (usable as a Depends() or called directly).

    LLM_PROVIDER=openrouter → OpenRouterClient (requires OPENROUTER_API_KEY)
    """
    from app.llm.base import LLMError
    settings = get_llm_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "openrouter":
        key = (settings.openrouter_api_key or "").strip()
        if not key or key == "your_openrouter_api_key_here":
            raise LLMError(
                "OpenRouter API key is missing or set to placeholder ('your_openrouter_api_key_here'). "
                "Please set a valid OPENROUTER_API_KEY in environment variables."
            )
        model_name = settings.llm_model or settings.openrouter_model or "auto"
        from app.llm.openrouter_client import OpenRouterClient
        return OpenRouterClient(
            api_key=key,
            model=model_name,
            timeout=settings.llm_timeout_seconds,
        )

    raise LLMError(f"Unsupported LLM provider: {provider}")
