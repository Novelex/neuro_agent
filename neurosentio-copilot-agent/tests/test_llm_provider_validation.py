"""Tests for LLM Provider Validation, Safety, and Fallbacks."""

import pytest
from app.llm.base import LLMError
from app.llm.client_factory import get_llm_client
from app.llm.mock_client import MockLLMClient
from app.llm.anthropic_client import AnthropicClient
from app.llm.openai_client import OpenAIClient
from app.core.llm_config import get_llm_settings


def test_mock_mode_is_default_and_keyless():
    """Asserts that mock mode is the default and does not require keys."""
    settings = get_llm_settings()
    # Save original
    original_provider = settings.llm_provider
    try:
        settings.llm_provider = "mock"
        client = get_llm_client()
        assert isinstance(client, MockLLMClient)
    finally:
        settings.llm_provider = original_provider


@pytest.mark.asyncio
async def test_anthropic_missing_key_raises_clean_llm_error():
    """Asserts that missing Anthropic API key raises a clean LLMError."""
    client = AnthropicClient(api_key="", model="claude-3-5-haiku-20241022")
    with pytest.raises(LLMError) as exc_info:
        await client.generate_json("system prompt", "user prompt")
    assert "Anthropic API key is missing" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_missing_key_raises_clean_llm_error():
    """Asserts that missing OpenAI API key raises a clean LLMError."""
    client = OpenAIClient(api_key="  ", model="gpt-4o-mini")
    with pytest.raises(LLMError) as exc_info:
        await client.generate_json("system prompt", "user prompt")
    assert "OpenAI API key is missing" in str(exc_info.value)


def test_llm_settings_defaults_are_safe():
    """Asserts default logging variables and credentials are key-free."""
    from app.core.llm_config import LLMSettings
    settings = LLMSettings(_env_file=None)
    assert settings.llm_provider == "mock"
    assert settings.anthropic_api_key == ""
    assert settings.openai_api_key == ""
    assert settings.llm_log_prompts is False
    assert settings.llm_log_responses is False
