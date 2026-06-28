import pytest
import os
from app.core.llm_config import get_llm_settings
from app.core.config import get_settings

@pytest.fixture(autouse=True)
def force_mock_llm_provider(monkeypatch):
    """Force mock LLM provider and default environment settings for all unit tests."""
    # Override LLM settings
    llm_settings = get_llm_settings()
    monkeypatch.setattr(llm_settings, "llm_provider", "mock")
    monkeypatch.setattr(llm_settings, "anthropic_api_key", "")
    monkeypatch.setattr(llm_settings, "openai_api_key", "")
    monkeypatch.setattr(llm_settings, "openrouter_api_key", "")

    # Override main App settings
    app_settings = get_settings()
    monkeypatch.setattr(app_settings, "app_env", "testing")
    monkeypatch.setattr(app_settings, "auth_required", False)
