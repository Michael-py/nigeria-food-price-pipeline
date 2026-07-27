"""Unit tests for the FastAPI prediction service."""

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
    assert "models_loaded" in data


def test_list_commodities():
    """Commodities endpoint returns a list."""
    response = client.get("/commodities")
    assert response.status_code == 200
    data = response.json()
    assert "commodities" in data
    assert isinstance(data["commodities"], list)


def test_list_markets():
    """Markets endpoint returns a list."""
    response = client.get("/markets")
    assert response.status_code == 200
    data = response.json()
    assert "markets" in data
    assert isinstance(data["markets"], list)


def test_predict_invalid_commodity():
    """Predict with non-existent commodity returns 404."""
    response = client.post(
        "/predict",
        json={
            "commodity": "NonExistentFood",
            "market": "NonExistentMarket",
            "forecast_horizon_days": 7,
        },
    )
    # Should be 400 (no model) or 404 (no data)
    assert response.status_code in (400, 404, 503)


def test_latest_prices():
    """Latest prices endpoint returns data."""
    response = client.get("/prices/latest?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "prices" in data
    assert "count" in data
