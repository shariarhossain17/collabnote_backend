"""Tests for FastAPI application."""
from fastapi.testclient import TestClient
from .main import app

client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint returns correct structure."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "instance_id" in data
    assert "hostname" in data


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "instance_id" in data


def test_missing_endpoint():
    """Test 404 error handling."""
    response = client.get("/nonexistent")
    assert response.status_code == 404

