"""Tests for GET /health endpoint."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_body():
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "neurosentio-copilot-agent"
