"""
LLM client base interface.

All providers must implement BaseLLMClient.
This keeps the decomposer service decoupled from any specific LLM provider.
"""

from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """
    Abstract base for all LLM providers.
    Returns a parsed Python dict — callers should validate the shape with Pydantic.
    """

    @abstractmethod
    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str = "",
    ) -> dict:
        """
        Call the LLM and return a parsed JSON dict.

        Args:
            system_prompt: Role/instructions for the model.
            user_prompt:   The actual request content.
            schema_name:   Optional label for logging/debugging.

        Returns:
            A Python dict containing the model's structured response.

        Raises:
            LLMError: if the call fails or returns invalid JSON.
        """
        ...


class LLMError(Exception):
    """Raised when an LLM call fails or returns unparseable output."""
    pass
