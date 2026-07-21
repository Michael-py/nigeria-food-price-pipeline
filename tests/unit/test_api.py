"""Unit tests for the FastAPI prediction service."""

import pytest
from fastapi.testclient import TestClient

from ml.serving.app import app

client = TestClient(app)


def test_health_endpoint():
    """Health endpoint returns 200 with status healthy."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_list_commodities():
    """Commodities endpoint returns a list."""
    response = client.get("/commodities")
    assert response.status_code == 200
    data = response.json()
    assert "commodities" in data
    assert len(data["commodities"]) > 0
    assert "Rice (imported)" in data["commodities"]


def test_list_markets():
    """Markets endpoint returns a list."""
    response = client.get("/markets")
    assert response.status_code == 200
    data = response.json()
    assert "markets" in data
    assert len(data["markets"]) > 0
    assert "Lagos (Mile 12)" in data["markets"]


def test_predict_not_implemented():
    """Predict endpoint returns 501 until implemented."""
    response = client.post(
        "/predict",
        json={
            "commodity": "Rice (imported)",
            "market": "Lagos (Mile 12)",
            "forecast_horizon_days": 7,
        },
    )
    assert response.status_code == 501
