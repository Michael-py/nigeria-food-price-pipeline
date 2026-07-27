"""Pydantic schemas for API request/response models."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    models_loaded: int = 0


class PredictionRequest(BaseModel):
    """Request body for price prediction."""

    commodity: str = Field(..., description="Commodity name (e.g., 'Rice (imported)')")
    market: str = Field(..., description="Market name (e.g., 'Maiduguri')")
    forecast_horizon_days: int = Field(
        default=7,
        ge=7,
        le=30,
        description="Forecast horizon: 7 or 30 days",
    )


class PredictionResponse(BaseModel):
    """Response body for price prediction."""

    commodity: str
    market: str
    forecast_date: date
    forecast_horizon_days: int
    predicted_price_ngn: float = Field(..., description="Predicted price in Naira")
    lower_bound_ngn: float = Field(..., description="Lower 95% confidence bound")
    upper_bound_ngn: float = Field(..., description="Upper 95% confidence bound")
    model_version: str
    unit: str = Field(default="NGN/kg", description="Price unit")
