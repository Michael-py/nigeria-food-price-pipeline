"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_wfp_data():
    """Sample WFP price data for testing."""
    return [
        {
            "market_name": "Lagos (Mile 12)",
            "commodity_name": "Rice (imported)",
            "currency_name": "NGN",
            "unit_name": "KG",
            "price": 1850.00,
            "price_date": "2026-07-01",
        },
        {
            "market_name": "Kano (Dawanau)",
            "commodity_name": "Maize",
            "currency_name": "NGN",
            "unit_name": "KG",
            "price": 920.00,
            "price_date": "2026-07-01",
        },
    ]


@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return [
        {
            "market_name": "Lagos (Mile 12)",
            "latitude": 6.5833,
            "longitude": 3.3833,
            "weather_date": "2026-07-01",
            "temperature_max": 29.5,
            "temperature_min": 24.2,
            "precipitation_mm": 12.3,
            "humidity_pct": 82.0,
        },
    ]
