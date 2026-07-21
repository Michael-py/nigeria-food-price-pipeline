"""Pydantic schemas for API request/response models."""

from datetime import date

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


class PredictionRequest(BaseModel):
    """Request body for price prediction."""

    commodity: str = Field(..., description="Commodity name (e.g., 'Rice (imported)')")
    market: str = Field(..., description="Market name (e.g., 'Lagos (Mile 12)')")
    forecast_horizon_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Number of days to forecast (1-30)",
    )


class PredictionResponse(BaseModel):
    """Response body for price prediction."""

    commodity: str
    market: str
    forecast_date: date
    forecast_horizon_days: int
    predicted_price_ngn: float = Field(..., description="Predicted price in Naira")
    lower_bound_ngn: float = Field(..., description="Lower confidence bound")
    upper_bound_ngn: float = Field(..., description="Upper confidence bound")
    model_version: str
    unit: str = Field(default="NGN/kg", description="Price unit")


class BatchPredictionResponse(BaseModel):
    """Response for batch predictions."""

    predictions: list[PredictionResponse]
    generated_at: str
    model_version: str
