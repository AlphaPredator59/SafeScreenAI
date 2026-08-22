"""Tests for public health checks."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_service_status() -> None:
    """The API exposes a successful versioned health check."""
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "SafeScreen AI"}
