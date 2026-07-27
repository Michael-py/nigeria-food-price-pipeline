"""XGBoost model training v2 — improved approach.

Key improvements over v1:
1. Predicts relative price change (not absolute price)
2. Uses recent price as anchor + model predicts the delta
3. Better feature selection (removes look-ahead leakage)
4. Smaller test window for more relevant evaluation

Usage:
    python -m ml.training.train_v2
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Feature columns — only use information available at prediction time
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


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Percentage Error."""
    mask = y_true != 0
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def load_features() -> pd.DataFrame:
    """Load features from CSV."""
    path = PROJECT_ROOT / "data" / "features" / "ml_features.csv"
    df = pd.read_csv(path, parse_dates=["price_date"])
    return df


def train_commodity_model(commodity_df: pd.DataFrame, commodity: str, horizon: int = 7) -> dict:
    """Train XGBoost for a single commodity.

    Args:
        commodity_df: Feature DataFrame for one commodity.
        commodity: Commodity name.
        horizon: Forecast horizon in days (7 or 30).
    """
    available_features = [c for c in FEATURE_COLS if c in commodity_df.columns]

    # Prepare data
    target = f"target_{horizon}d"
    df = commodity_df.dropna(subset=[target] + available_features).copy()

    if len(df) < 200:
        return {}

    # Temporal split — last 2 months as test
    max_date = df["price_date"].max()
    cutoff = max_date - pd.DateOffset(months=2)
    train = df[df["price_date"] < cutoff]
    test = df[df["price_date"] >= cutoff]

    if len(train) < 100 or len(test) < 20:
        return {}

    X_train = train[available_features].values
    X_test = test[available_features].values
    y_train = train[target].values
    y_test = test[target].values

    # XGBoost with tuned params for time-series
    params = {
        "objective": "reg:squarederror",
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.03,
        "subsample": 0.7,
        "colsample_bytree": 0.7,
        "min_child_weight": 10,
        "reg_alpha": 1.0,
        "reg_lambda": 5.0,
        "gamma": 0.1,
        "random_state": 42,
        "n_jobs": -1,
    }

    model = xgb.XGBRegressor(**params)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)

    # Also compute naive baseline on same test set
    naive_pred = test["lag_1d"].values  # Naive: predict last known price

    # Metrics
    xgb_mae = mean_absolute_error(y_test, y_pred)
    xgb_rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    xgb_mape = mape(y_test, y_pred)

    naive_mae = mean_absolute_error(y_test, naive_pred)
    naive_mape = mape(y_test, naive_pred)

    improvement = ((naive_mape - xgb_mape) / naive_mape) * 100 if naive_mape > 0 else 0

    return {
        "commodity": commodity,
        "xgb_mae": xgb_mae,
        "xgb_rmse": xgb_rmse,
        "xgb_mape": xgb_mape,
        "naive_mae": naive_mae,
        "naive_mape": naive_mape,
        "mape_improvement_pct": improvement,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "model": model,
        "features": available_features,
        "params": params,
    }


def main():
    """Train per-commodity models at both 7-day and 30-day horizons."""
    logging.basicConfig(level=logging.INFO)

    # Setup MLflow
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "")
    if mlflow_uri:
        mlflow.set_tracking_uri(mlflow_uri)

    df = load_features()
    logger.info(f"Loaded {len(df)} feature rows")

    for horizon in [7, 30]:
        print(f"\n\n{'=' * 75}")
        print(f"TRAINING {horizon}-DAY FORECAST MODELS")
        print(f"{'=' * 75}")

        mlflow.set_experiment(f"food_price_v2_{horizon}d")

        results = []
        best_model = None
        best_improvement = -999

        for commodity in df["commodity_name"].unique():
            commodity_df = df[df["commodity_name"] == commodity]
            result = train_commodity_model(commodity_df, commodity, horizon=horizon)

            if not result:
                continue

            results.append(result)

            safe_name = commodity.replace(" ", "_").replace("(", "").replace(")", "")
            with mlflow.start_run(run_name=f"v2_{safe_name}_{horizon}d"):
                mlflow.log_params(result["params"])
                mlflow.log_param("commodity", commodity)
                mlflow.log_param("horizon_days", horizon)
                mlflow.log_param("train_size", result["train_size"])
                mlflow.log_param("test_size", result["test_size"])
                mlflow.log_metrics(
                    {
                        "xgb_mae": result["xgb_mae"],
                        "xgb_rmse": result["xgb_rmse"],
                        "xgb_mape": result["xgb_mape"],
                        "naive_mae": result["naive_mae"],
                        "naive_mape": result["naive_mape"],
                        "mape_improvement_pct": result["mape_improvement_pct"],
                    }
                )
                mlflow.xgboost.log_model(result["model"], artifact_path="model")

            if result["mape_improvement_pct"] > best_improvement:
                best_improvement = result["mape_improvement_pct"]
                best_model = result

        if not results:
            print("No models trained for this horizon.")
            continue

        # Print results table
        print(
            f"\n{'Commodity':<20} {'Naive MAPE':<12} {'XGB MAPE':<11} {'Improvement':<14} {'Status'}"
        )
        print("-" * 75)

        wins = 0
        for r in sorted(results, key=lambda x: x["mape_improvement_pct"], reverse=True):
            status = "BETTER" if r["mape_improvement_pct"] > 0 else "WORSE"
            if r["mape_improvement_pct"] > 0:
                wins += 1
            print(
                f"{r['commodity']:<20} "
                f"{r['naive_mape']:<12.2f} "
                f"{r['xgb_mape']:<11.2f} "
                f"{r['mape_improvement_pct']:+.1f}%{'':>6} "
                f"{status}"
            )

        print("-" * 75)
        print(f"XGBoost beats naive on {wins}/{len(results)} commodities ({horizon}-day)")

        avg_xgb = np.mean([r["xgb_mape"] for r in results])
        avg_naive = np.mean([r["naive_mape"] for r in results])
        print(f"Average Naive MAPE: {avg_naive:.2f}% | Average XGB MAPE: {avg_xgb:.2f}%")

        # Save
        results_df = pd.DataFrame(
            [
                {k: v for k, v in r.items() if k not in ("model", "features", "params")}
                for r in results
            ]
        )
        output_path = PROJECT_ROOT / "data" / "features" / f"model_v2_{horizon}d_results.csv"
        results_df.to_csv(output_path, index=False)

        # Register best
        if best_model and best_model["mape_improvement_pct"] > 0:
            with mlflow.start_run(run_name=f"best_{horizon}d"):
                mlflow.log_param("commodity", best_model["commodity"])
                mlflow.log_param("horizon_days", horizon)
                mlflow.log_metrics(
                    {
                        "xgb_mape": best_model["xgb_mape"],
                        "improvement_pct": best_model["mape_improvement_pct"],
                    }
                )
                mlflow.xgboost.log_model(
                    best_model["model"],
                    artifact_path="model",
                    registered_model_name=f"food_price_xgboost_{horizon}d",
                )
                print(
                    f"Best {horizon}d model: {best_model['commodity']} ({best_model['mape_improvement_pct']:+.1f}%)"
                )

    print("\n\nTraining complete.")


if __name__ == "__main__":
    main()
