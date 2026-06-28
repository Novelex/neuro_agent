"""Unit tests for OpenRouter cheapest model routing and client rate limiting."""

import pytest
import time
import asyncio
from unittest.mock import patch, AsyncMock
from app.llm.openrouter_client import OpenRouterClient, TokenBucketRateLimiter, LLMError


@pytest.mark.asyncio
async def test_token_bucket_rate_limiter():
    """Verify that TokenBucketRateLimiter correctly throttles concurrent requests."""
    # Capacity = 1, Rate = 1 token/sec
    limiter = TokenBucketRateLimiter(rate=5.0, capacity=1.0)

    t0 = time.monotonic()
    # First acquire should be instant (starts at full capacity)
    await limiter.acquire()
    
    # Second acquire should wait/throttle because capacity is empty
    await limiter.acquire()
    elapsed = time.monotonic() - t0

    # Minimum elapsed time should be close to 0.2s (since rate=5 token/sec)
    assert elapsed >= 0.15


@pytest.mark.asyncio
async def test_openrouter_cheapest_model_routing():
    """Verify that OpenRouterClient resolves and caches the cheapest model."""
    client = OpenRouterClient(api_key="test-key", model="auto")

    # Reset cache before testing
    OpenRouterClient._cached_cheapest_model = None
    OpenRouterClient._cache_time = 0.0

    mock_models_response = {
        "data": [
            {
                "id": "expensive/model",
                "name": "Expensive Model",
                "pricing": {"prompt": "0.00001", "completion": "0.00003"}
            },
            {
                "id": "cheap/model",
                "name": "Cheap Model",
                "pricing": {"prompt": "0.0000001", "completion": "0.0000002"}
            }
        ]
    }

    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    # Mock httpx.AsyncClient.get
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MockResponse(mock_models_response, 200)

        # Call get_model_id the first time (should hit mock API)
        model_id_1 = await client._get_model_id()
        assert model_id_1 == "expensive/model"  # First model in OpenRouter response (sorted by their API)
        assert mock_get.call_count == 1

        # Call get_model_id the second time (should hit cache and NOT call API)
        model_id_2 = await client._get_model_id()
        assert model_id_2 == "expensive/model"
        assert mock_get.call_count == 1  # Still 1


@pytest.mark.asyncio
async def test_openrouter_cheapest_model_routing_fallback():
    """Verify that OpenRouterClient falls back to a default model if query fails."""
    client = OpenRouterClient(api_key="test-key", model="auto")

    # Reset cache before testing
    OpenRouterClient._cached_cheapest_model = None
    OpenRouterClient._cache_time = 0.0

    # Mock httpx.AsyncClient.get to throw exception
    with patch("httpx.AsyncClient.get", side_effect=Exception("API connection down")):
        model_id = await client._get_model_id()
        assert model_id == "google/gemini-2.5-flash:free"
