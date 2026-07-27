"""Baseline models for food price forecasting.

Implements simple baselines to benchmark against:
1. Naive (last value carried forward)
2. Moving Average (30-day)
3. ARIMA (statistical time-series model)

Usage:
    python -m ml.training.baselines
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def mean_absolute_percentage_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate MAPE, handling zeros."""
    mask = y_true != 0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def load_features() -> pd.DataFrame:
    """Load the feature table from CSV."""
    csv_path = PROJECT_ROOT / "data" / "features" / "ml_features.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Feature file not found: {csv_path}. Run feature engineering first."
        )

    df = pd.read_csv(csv_path, parse_dates=["price_date"])
    logger.info(f"Loaded {len(df)} rows from features CSV")
    return df


def train_test_split_temporal(df: pd.DataFrame, test_months: int = 3):
    """Split data temporally — last N months as test set.

    Args:
        df: Feature DataFrame.
        test_months: Number of months to hold out for testing.

    Returns:
        Tuple of (train_df, test_df).
    """
    max_date = df["price_date"].max()
    cutoff = max_date - pd.DateOffset(months=test_months)

    train = df[df["price_date"] < cutoff].copy()
    test = df[df["price_date"] >= cutoff].copy()

    logger.info(
        f"Train: {len(train)} rows (up to {cutoff.date()}) | "
        f"Test: {len(test)} rows ({cutoff.date()} to {max_date.date()})"
    )
    return train, test


def evaluate_naive_baseline(test_df: pd.DataFrame) -> dict:
    """Naive baseline: predict using the last known price (lag_1d).

    Returns:
        Dict with MAE, RMSE, MAPE metrics.
    """
    valid = test_df.dropna(subset=["target_7d", "lag_1d"])
    if valid.empty:
        return {"mae": np.nan, "rmse": np.nan, "mape": np.nan}

    y_true = valid["target_7d"].values
    y_pred = valid["lag_1d"].values  # Predict next week = today's price

    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": np.sqrt(mean_squared_error(y_true, y_pred)),
        "mape": mean_absolute_percentage_error(y_true, y_pred),
    }


def evaluate_moving_average_baseline(test_df: pd.DataFrame) -> dict:
    """Moving Average baseline: predict using 30-day rolling mean.

    Returns:
        Dict with MAE, RMSE, MAPE metrics.
    """
    valid = test_df.dropna(subset=["target_7d", "roll_mean_30d"])
    if valid.empty:
        return {"mae": np.nan, "rmse": np.nan, "mape": np.nan}

    y_true = valid["target_7d"].values
    y_pred = valid["roll_mean_30d"].values

    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": np.sqrt(mean_squared_error(y_true, y_pred)),
        "mape": mean_absolute_percentage_error(y_true, y_pred),
    }


def evaluate_seasonal_naive(test_df: pd.DataFrame) -> dict:
    """Seasonal naive: predict using price from 30 days ago.

    Returns:
        Dict with MAE, RMSE, MAPE metrics.
    """
    valid = test_df.dropna(subset=["target_7d", "lag_30d"])
    if valid.empty:
        return {"mae": np.nan, "rmse": np.nan, "mape": np.nan}

    y_true = valid["target_7d"].values
    y_pred = valid["lag_30d"].values

    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": np.sqrt(mean_squared_error(y_true, y_pred)),
        "mape": mean_absolute_percentage_error(y_true, y_pred),
    }


def run_baselines() -> pd.DataFrame:
    """Run all baseline models and return comparison table.

    Returns:
        DataFrame with model name, MAE, RMSE, MAPE per commodity.
    """
    df = load_features()
    train, test = train_test_split_temporal(df, test_months=3)

    results = []

    for commodity in df["commodity_name"].unique():
        commodity_test = test[test["commodity_name"] == commodity]

        if len(commodity_test) < 10:
            continue

        # Naive
        naive = evaluate_naive_baseline(commodity_test)
        results.append(
            {
                "commodity": commodity,
                "model": "Naive (last value)",
                **naive,
            }
        )

        # Moving Average
        ma = evaluate_moving_average_baseline(commodity_test)
        results.append(
            {
                "commodity": commodity,
                "model": "Moving Average (30d)",
                **ma,
            }
        )

        # Seasonal Naive
        sn = evaluate_seasonal_naive(commodity_test)
        results.append(
            {
                "commodity": commodity,
                "model": "Seasonal Naive (30d)",
                **sn,
            }
        )

    results_df = pd.DataFrame(results)
    return results_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Running baseline models...")
    results = run_baselines()

    if not results.empty:
        print("\n" + "=" * 70)
        print("BASELINE MODEL RESULTS (7-day forecast)")
        print("=" * 70)

        # Summary by model type
        summary = (
            results.groupby("model")
            .agg(
                avg_mae=("mae", "mean"),
                avg_rmse=("rmse", "mean"),
                avg_mape=("mape", "mean"),
            )
            .round(2)
        )

        print("\nOverall averages across all commodities:")
        print(summary.to_string())

        # Per commodity (best model)
        print("\nBest baseline per commodity (lowest MAE):")
        best = results.loc[results.groupby("commodity")["mae"].idxmin()]
        print(best[["commodity", "model", "mae", "mape"]].to_string(index=False))

        # Save results
        output_path = PROJECT_ROOT / "data" / "features" / "baseline_results.csv"
        results.to_csv(output_path, index=False)
        print(f"\nResults saved to {output_path}")
    else:
        print("No baseline results generated.")
