"""FastAPI application for food price prediction serving.

Provides REST endpoints for:
- Price predictions (7-day and 30-day forecasts)
- Available commodities and markets
- Health checks
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ml.serving.schemas import (
    HealthResponse,
    PredictionRequest,
    PredictionResponse,
)

app = FastAPI(
    title="Nigeria Food Price Forecast API",
    description="ML-powered food price predictions for Nigerian commodity markets",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check API health status."""
    return HealthResponse(status="healthy", version="0.1.0")


@app.get("/commodities")
async def list_commodities() -> dict[str, list[str]]:
    """List available commodities for forecasting."""
    # TODO: Query database for available commodities
    return {
        "commodities": [
            "Rice (imported)",
            "Rice (local)",
            "Maize",
            "Beans (white)",
            "Garri (white)",
            "Yam tuber",
            "Palm oil",
            "Groundnut oil",
            "Tomato",
            "Onion",
        ]
    }


@app.get("/markets")
async def list_markets() -> dict[str, list[str]]:
    """List available markets for forecasting."""
    # TODO: Query database for available markets
    return {
        "markets": [
            "Lagos (Mile 12)",
            "Kano (Dawanau)",
            "Abuja (Wuse)",
            "Port Harcourt",
            "Ibadan (Bodija)",
        ]
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest) -> PredictionResponse:
    """Generate price forecast for a commodity in a market.

    Args:
        request: Prediction request with commodity, market, and horizon.

    Returns:
        Price prediction with confidence intervals.
    """
    # TODO: Load model from MLflow, generate features, predict
    raise HTTPException(
        status_code=501,
        detail="Prediction endpoint not yet implemented. See Week 7 tasks.",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
