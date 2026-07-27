"""XGBoost model training for food price forecasting.

Trains an XGBoost regressor for each target commodity, tracks experiments
with MLflow, and registers the best model.

Usage:
    python -m ml.training.train
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

# MLflow setup — use local file store if no tracking server
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "")
# Empty string means MLflow will use ./mlruns in the current directory

# Feature columns used for training
FEATURE_COLS = [
    "lag_1d",
    "lag_3d",
    "lag_7d",
    "lag_14d",
    "lag_21d",
    "lag_30d",
    "lag_60d",
    "lag_90d",
    "roll_mean_7d",
    "roll_mean_14d",
    "roll_mean_30d",
    "roll_mean_60d",
    "roll_std_7d",
    "roll_std_14d",
    "roll_std_30d",
    "roll_std_60d",
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
    "cal_week_of_year",
    "cal_is_rainy_season",
    "cal_is_lean_season",
]

TARGET_COL = "target_7d"


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Percentage Error."""
    mask = y_true != 0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def load_features() -> pd.DataFrame:
    """Load features from CSV."""
    path = PROJECT_ROOT / "data" / "features" / "ml_features.csv"
    df = pd.read_csv(path, parse_dates=["price_date"])
    logger.info(f"Loaded {len(df)} rows")
    return df


def prepare_data(df: pd.DataFrame, test_months: int = 3):
    """Prepare train/test split with temporal ordering.

    Returns:
        Tuple of (X_train, X_test, y_train, y_test, test_df)
    """
    # Only keep rows with valid target
    df = df.dropna(subset=[TARGET_COL])

    # Available features (some may be missing)
    available_features = [c for c in FEATURE_COLS if c in df.columns]
    df = df.dropna(subset=available_features)

    # Temporal split
    max_date = df["price_date"].max()
    cutoff = max_date - pd.DateOffset(months=test_months)

    train = df[df["price_date"] < cutoff]
    test = df[df["price_date"] >= cutoff]

    X_train = train[available_features].values
    X_test = test[available_features].values
    y_train = train[TARGET_COL].values
    y_test = test[TARGET_COL].values

    logger.info(f"Train: {len(X_train)} rows | Test: {len(X_test)} rows")
    logger.info(f"Features: {len(available_features)}")

    return X_train, X_test, y_train, y_test, test, available_features


def train_global_model(df: pd.DataFrame) -> dict:
    """Train a single global XGBoost model across all commodities and markets.

    This approach uses commodity/market as implicit features through the
    lag and rolling statistics (which differ per series).

    Returns:
        Dict with metrics and model info.
    """
    if MLFLOW_TRACKING_URI:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("food_price_forecasting")

    X_train, X_test, y_train, y_test, test_df, feature_names = prepare_data(df)

    if len(X_train) == 0 or len(X_test) == 0:
        logger.error("No training or test data available")
        return {}

    # XGBoost parameters
    params = {
        "objective": "reg:squarederror",
        "n_estimators": 500,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "random_state": 42,
        "n_jobs": -1,
    }

    with mlflow.start_run(run_name="xgboost_global_7d"):
        # Log parameters
        mlflow.log_params(params)
        mlflow.log_param("target", TARGET_COL)
        mlflow.log_param("n_features", len(feature_names))
        mlflow.log_param("train_size", len(X_train))
        mlflow.log_param("test_size", len(X_test))
        mlflow.log_param("n_commodities", df["commodity_name"].nunique())
        mlflow.log_param("n_markets", df["market_name"].nunique())

        # Train
        logger.info("Training XGBoost model...")
        model = xgb.XGBRegressor(**params)
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        # Predict
        y_pred = model.predict(X_test)

        # Metrics
        mae_val = mean_absolute_error(y_test, y_pred)
        rmse_val = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mape_val = mape(y_test, y_pred)

        metrics = {
            "mae": mae_val,
            "rmse": rmse_val,
            "mape": mape_val,
        }

        # Log metrics
        mlflow.log_metrics(metrics)

        # Feature importance
        importance = pd.DataFrame(
            {
                "feature": feature_names,
                "importance": model.feature_importances_,
            }
        ).sort_values("importance", ascending=False)

        importance_path = PROJECT_ROOT / "data" / "features" / "feature_importance.csv"
        importance.to_csv(importance_path, index=False)
        mlflow.log_artifact(str(importance_path))

        # Log model
        mlflow.xgboost.log_model(
            model,
            artifact_path="model",
            registered_model_name="food_price_xgboost_7d",
        )

        # Per-commodity metrics
        commodity_metrics = []
        for commodity in test_df["commodity_name"].unique():
            mask = test_df["commodity_name"].values == commodity
            if mask.sum() < 10:
                continue
            c_y_true = y_test[mask[: len(y_test)]] if len(mask) == len(test_df) else y_test
            c_y_pred = y_pred[mask[: len(y_pred)]] if len(mask) == len(test_df) else y_pred

            # Only use if mask aligns
            if len(mask) == len(y_test):
                c_y_true = y_test[mask]
                c_y_pred = y_pred[mask]
                c_mae = mean_absolute_error(c_y_true, c_y_pred)
                c_mape = mape(c_y_true, c_y_pred)
                commodity_metrics.append(
                    {
                        "commodity": commodity,
                        "mae": c_mae,
                        "mape": c_mape,
                        "n_obs": int(mask.sum()),
                    }
                )
                mlflow.log_metric(
                    f"mae_{commodity.replace(' ', '_').replace('(', '').replace(')', '')}", c_mae
                )
                mlflow.log_metric(
                    f"mape_{commodity.replace(' ', '_').replace('(', '').replace(')', '')}", c_mape
                )

        logger.info(
            f"Global model — MAE: {mae_val:.2f}, RMSE: {rmse_val:.2f}, MAPE: {mape_val:.2f}%"
        )

        run_id = mlflow.active_run().info.run_id

    return {
        "run_id": run_id,
        "metrics": metrics,
        "feature_importance": importance,
        "commodity_metrics": pd.DataFrame(commodity_metrics)
        if commodity_metrics
        else pd.DataFrame(),
    }


def train_per_commodity_models(df: pd.DataFrame) -> pd.DataFrame:
    """Train separate XGBoost models per commodity.

    Returns:
        DataFrame with per-commodity results.
    """
    if MLFLOW_TRACKING_URI:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("food_price_per_commodity")

    results = []
    available_features = [c for c in FEATURE_COLS if c in df.columns]

    for commodity in df["commodity_name"].unique():
        commodity_df = df[df["commodity_name"] == commodity].copy()
        commodity_df = commodity_df.dropna(subset=[TARGET_COL] + available_features)

        if len(commodity_df) < 100:
            logger.warning(f"Skipping {commodity}: only {len(commodity_df)} rows")
            continue

        # Temporal split
        max_date = commodity_df["price_date"].max()
        cutoff = max_date - pd.DateOffset(months=3)
        train = commodity_df[commodity_df["price_date"] < cutoff]
        test = commodity_df[commodity_df["price_date"] >= cutoff]

        if len(train) < 50 or len(test) < 10:
            continue

        X_train = train[available_features].values
        X_test = test[available_features].values
        y_train = train[TARGET_COL].values
        y_test = test[TARGET_COL].values

        params = {
            "objective": "reg:squarederror",
            "n_estimators": 300,
            "max_depth": 5,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "n_jobs": -1,
        }

        with mlflow.start_run(run_name=f"xgb_{commodity.replace(' ', '_')}"):
            mlflow.log_params(params)
            mlflow.log_param("commodity", commodity)
            mlflow.log_param("train_size", len(X_train))
            mlflow.log_param("test_size", len(X_test))

            model = xgb.XGBRegressor(**params)
            model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

            y_pred = model.predict(X_test)

            mae_val = mean_absolute_error(y_test, y_pred)
            rmse_val = float(np.sqrt(mean_squared_error(y_test, y_pred)))
            mape_val = mape(y_test, y_pred)

            mlflow.log_metrics({"mae": mae_val, "rmse": rmse_val, "mape": mape_val})
            mlflow.xgboost.log_model(model, artifact_path="model")

            results.append(
                {
                    "commodity": commodity,
                    "mae": mae_val,
                    "rmse": rmse_val,
                    "mape": mape_val,
                    "train_size": len(X_train),
                    "test_size": len(X_test),
                }
            )

            logger.info(f"  {commodity}: MAE={mae_val:.2f}, MAPE={mape_val:.2f}%")

    return pd.DataFrame(results)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("XGBOOST MODEL TRAINING")
    print("=" * 60)

    # Load features
    df = load_features()

    # Train global model
    print("\n--- Global Model (all commodities) ---")
    global_result = train_global_model(df)

    if global_result:
        print("\nGlobal Model Results:")
        print(f"  MAE:  {global_result['metrics']['mae']:.2f} NGN")
        print(f"  RMSE: {global_result['metrics']['rmse']:.2f} NGN")
        print(f"  MAPE: {global_result['metrics']['mape']:.2f}%")
        print(f"  MLflow Run ID: {global_result['run_id']}")

        print("\nTop 10 Features:")
        print(global_result["feature_importance"].head(10).to_string(index=False))

    # Train per-commodity models
    print("\n\n--- Per-Commodity Models ---")
    commodity_results = train_per_commodity_models(df)

    if not commodity_results.empty:
        print("\nPer-Commodity Results:")
        print(commodity_results.sort_values("mape").to_string(index=False))

        # Save comparison
        output_path = PROJECT_ROOT / "data" / "features" / "model_comparison.csv"
        commodity_results.to_csv(output_path, index=False)

        # Compare vs baselines
        baseline_path = PROJECT_ROOT / "data" / "features" / "baseline_results.csv"
        if baseline_path.exists():
            baselines = pd.read_csv(baseline_path)
            naive_baselines = baselines[baselines["model"] == "Naive (last value)"]

            print("\n\n--- XGBoost vs Naive Baseline ---")
            print(f"{'Commodity':<20} {'Naive MAPE':<12} {'XGB MAPE':<12} {'Improvement'}")
            print("-" * 60)
            for _, row in commodity_results.iterrows():
                baseline = naive_baselines[naive_baselines["commodity"] == row["commodity"]]
                if not baseline.empty:
                    b_mape = baseline.iloc[0]["mape"]
                    improvement = ((b_mape - row["mape"]) / b_mape) * 100
                    print(
                        f"{row['commodity']:<20} {b_mape:<12.2f} {row['mape']:<12.2f} {improvement:+.1f}%"
                    )

    print(
        "\n\nTraining complete. View experiments at: mlflow ui --backend-store-uri",
        MLFLOW_TRACKING_URI,
    )
