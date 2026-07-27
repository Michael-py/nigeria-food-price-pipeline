"""FastAPI application for food price prediction serving.

Provides REST endpoints for:
- Price predictions (7-day and 30-day forecasts)
- Available commodities and markets
- Historical prices
- Health checks

Usage:
    uvicorn ml.serving.app:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ml.serving.schemas import (
    HealthResponse,
    PredictionRequest,
    PredictionResponse,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

app = FastAPI(
    title="Nigeria Food Price Forecast API",
    description="ML-powered food price predictions for Nigerian commodity markets",
    version="1.0.0",
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

# --- Model Loading ---

_models: dict[str, xgb.XGBRegressor] = {}
_features_df: Optional[pd.DataFrame] = None


def _load_models() -> None:
    """Load trained XGBoost models from MLflow artifacts."""
    global _models

    mlruns_dir = PROJECT_ROOT / "mlruns"
    if not mlruns_dir.exists():
        logger.warning("No mlruns directory found. Predictions unavailable.")
        return

    # Find model.xgb files in the mlruns directory
    model_files = list(mlruns_dir.rglob("model.xgb"))
    if not model_files:
        model_files = list(mlruns_dir.rglob("model.ubj"))

    if not model_files:
        logger.warning("No model artifacts found in mlruns/")
        return

    # Load the most recent model (largest path = latest run typically)
    # Use the last model file found as the default for both horizons
    latest_model_path = sorted(model_files)[-1]
    model = xgb.XGBRegressor()
    model.load_model(str(latest_model_path))

    # Register for both horizons (same model architecture)
    _models["7d"] = model
    _models["30d"] = model
    logger.info(f"Loaded model from {latest_model_path} (serving for 7d and 30d)")


def _load_features() -> pd.DataFrame:
    """Load the features CSV for generating predictions."""
    global _features_df
    if _features_df is None:
        path = PROJECT_ROOT / "data" / "features" / "ml_features.csv"
        if path.exists():
            _features_df = pd.read_csv(path, parse_dates=["price_date"])
            logger.info(f"Loaded features: {len(_features_df)} rows")
        else:
            _features_df = pd.DataFrame()
    return _features_df


# Load models on startup (lazy — deferred until first prediction)
# _load_models() is called on first /predict request instead


# --- Feature columns (must match training) ---
FEATURE_COLS = [
    "lag_1d",
    "lag_3d",
    "lag_7d",
    "lag_14d",
    "lag_30d",
    "lag_60d",
    "lag_90d",
    "roll_mean_7d",
    "roll_mean_14d",
    "roll_mean_30d",
    "roll_std_7d",
    "roll_std_14d",
    "roll_std_30d",
    "roll_min_7d",
    "roll_min_30d",
    "roll_max_7d",
    "roll_max_30d",
    "mom_pct_change_7d",
    "mom_pct_change_14d",
    "mom_pct_change_30d",
    "cal_month",
    "cal_quarter",
    "cal_day_of_year",
    "cal_is_rainy_season",
    "cal_is_lean_season",
]


# --- Endpoints ---


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check API health status."""
    models_loaded = len(_models)
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        models_loaded=models_loaded,
    )


@app.get("/commodities")
async def list_commodities() -> dict[str, list[str]]:
    """List available commodities for forecasting."""
    df = _load_features()
    if df.empty:
        return {"commodities": []}
    commodities = sorted(df["commodity_name"].unique().tolist())
    return {"commodities": commodities}


@app.get("/markets")
async def list_markets() -> dict[str, list[str]]:
    """List available markets for forecasting."""
    df = _load_features()
    if df.empty:
        return {"markets": []}
    markets = sorted(df["market_name"].unique().tolist())
    return {"markets": markets}


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest) -> PredictionResponse:
    """Generate price forecast for a commodity in a market.

    Uses the latest available features to predict future price.
    """
    # Lazy-load models on first request
    if not _models:
        _load_models()

    horizon_key = f"{request.forecast_horizon_days}d"

    # Validate horizon
    if horizon_key not in _models:
        available = list(_models.keys())
        raise HTTPException(
            status_code=400,
            detail=f"No model for {request.forecast_horizon_days}-day horizon. Available: {available}",
        )

    model = _models[horizon_key]
    df = _load_features()

    if df.empty:
        raise HTTPException(status_code=503, detail="Feature data not loaded")

    # Find the latest data point for this commodity+market
    mask = (df["commodity_name"] == request.commodity) & (df["market_name"] == request.market)
    subset = df[mask].sort_values("price_date", ascending=False)

    if subset.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data for {request.commodity} in {request.market}",
        )

    # Get the most recent row with features
    available_features = [c for c in FEATURE_COLS if c in subset.columns]
    latest = subset.dropna(subset=available_features).head(1)

    if latest.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient feature data for {request.commodity} in {request.market}",
        )

    # Predict
    X = latest[available_features].values
    predicted_price = float(model.predict(X)[0])

    # Simple confidence interval based on historical volatility
    recent_std = (
        subset["roll_std_30d"].iloc[0]
        if "roll_std_30d" in subset.columns
        else predicted_price * 0.1
    )
    if pd.isna(recent_std):
        recent_std = predicted_price * 0.1

    lower = max(0, predicted_price - 1.96 * recent_std)
    upper = predicted_price + 1.96 * recent_std

    forecast_date = latest["price_date"].iloc[0] + timedelta(days=request.forecast_horizon_days)

    return PredictionResponse(
        commodity=request.commodity,
        market=request.market,
        forecast_date=forecast_date.date() if hasattr(forecast_date, "date") else forecast_date,
        forecast_horizon_days=request.forecast_horizon_days,
        predicted_price_ngn=round(predicted_price, 2),
        lower_bound_ngn=round(lower, 2),
        upper_bound_ngn=round(upper, 2),
        model_version=horizon_key,
        unit="NGN/kg",
    )


@app.get("/prices/latest")
async def latest_prices(
    commodity: Optional[str] = Query(None, description="Filter by commodity"),
    market: Optional[str] = Query(None, description="Filter by market"),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """Get latest observed prices."""
    df = _load_features()
    if df.empty:
        return {"prices": [], "count": 0}

    result = df[["price_date", "market_name", "commodity_name", "price_ngn"]].copy()

    if commodity:
        result = result[result["commodity_name"] == commodity]
    if market:
        result = result[result["market_name"] == market]

    result = result.sort_values("price_date", ascending=False).head(limit)
    result["price_date"] = result["price_date"].dt.strftime("%Y-%m-%d")

    return {
        "prices": result.to_dict(orient="records"),
        "count": len(result),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
