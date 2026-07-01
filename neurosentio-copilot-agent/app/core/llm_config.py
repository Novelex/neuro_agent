"""
LLM configuration settings — hardened for Day 9.
Loaded from environment variables / .env file.
"""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache


class LLMSettings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Provider ──────────────────────────────────────────────────────
    # Which LLM provider to use: mock | anthropic | openai | openrouter
    llm_provider: str = "mock"

    # API keys — intentionally empty by default so the app runs key-free
    openrouter_api_key: str = ""

    # Model name — if empty, services use sensible defaults
    llm_model: str = ""

    # Optional model defaults (used when llm_model is empty)
    openrouter_model: str = "google/gemini-2.0-flash-lite-preview-02-05:free"

    # ── Request behaviour ─────────────────────────────────────────────
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 1

    # ── Logging control — privacy-safe defaults ───────────────────────
    # Set true only in controlled dev environments.
    # Never log in production without explicit data handling policies.
    llm_log_prompts: bool = False
    llm_log_responses: bool = False

    # ── Rate limiting ─────────────────────────────────────────────────
    llm_daily_user_limit: int = 50
    llm_monthly_user_limit: int = 1000

    # ── Real provider tests & prompt evaluation ────────────────────────
    # Disabled by default. Requires a real API key.
    # Enable only in explicit integration/smoke test runs.
    llm_enable_real_provider_tests: bool = False
    llm_enable_prompt_eval: bool = False


@lru_cache()
def get_llm_settings() -> LLMSettings:
    return LLMSettings()
