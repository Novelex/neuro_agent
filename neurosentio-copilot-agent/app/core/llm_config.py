"""
LLM configuration settings.
Loaded from environment variables / .env file.
"""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache


class LLMSettings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Which LLM provider to use: mock | anthropic | openai
    llm_provider: str = "mock"

    # API keys — intentionally empty by default so the app runs key-free
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Model name (provider-specific, ignored by mock)
    llm_model: str = ""

    # Request timeout in seconds
    llm_timeout_seconds: int = 30


@lru_cache()
def get_llm_settings() -> LLMSettings:
    return LLMSettings()
