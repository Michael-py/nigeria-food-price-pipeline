"""Feature engineering for food price forecasting.

Generates time-series features from the mart tables:
- Lag features (1, 7, 14, 30 day lags)
- Rolling statistics (7, 14, 30 day mean, std)
- Price momentum (% change over windows)
- Calendar features (month, quarter, day of week)
- Seasonality indicators (rainy season, dry season, lean season)

Usage:
    python -m ml.features.feature_engineering
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from ingestion.utils.config import get_database_url

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Target commodities for modeling (high data volume, economically important)
TARGET_COMMODITIES = [
    "Millet",
    "Rice (imported)",
    "Rice (local)",
    "Sorghum",
    "Yam",
    "Maize flour",
    "Groundnuts",
    "Onions",
    "Eggs",
    "Oil (palm)",
]

# Minimum observations required for a market-commodity pair
MIN_OBSERVATIONS = 50


def load_price_data() -> pd.DataFrame:
    """Load daily prices from the marts layer.

    Returns:
        DataFrame with price_date, market_name, commodity_name, price_ngn.
    """
    engine = create_engine(get_database_url())

    query = text("""
        SELECT price_date, market_name, commodity_name, price_ngn
        FROM public_marts.fct_daily_prices
        WHERE commodity_name = ANY(:commodities)
        ORDER BY market_name, commodity_name, price_date
    """)

    df = pd.read_sql(query, engine, params={"commodities": TARGET_COMMODITIES})
    df["price_date"] = pd.to_datetime(df["price_date"])
    logger.info(
        f"Loaded {len(df)} price observations for {df['commodity_name'].nunique()} commodities"
    )
    return df


def load_exchange_rates() -> pd.DataFrame:
    """Load exchange rate data for feature enrichment."""
    engine = create_engine(get_database_url())

    query = text("""
        SELECT rate_date, central_rate as usd_ngn_rate
        FROM public_staging.stg_cbn_rates
        WHERE currency = 'USD'
        ORDER BY rate_date
    """)

    df = pd.read_sql(query, engine)
    if not df.empty:
        df["rate_date"] = pd.to_datetime(df["rate_date"])
    return df


def generate_features(df: pd.DataFrame) -> pd.DataFrame:
    """Generate all features for each market-commodity time series.

    Args:
        df: DataFrame with price_date, market_name, commodity_name, price_ngn.

    Returns:
        DataFrame with original columns + engineered features + target column.
    """
    logger.info("Generating features...")

    # Sort by group and date
    df = df.sort_values(["market_name", "commodity_name", "price_date"]).reset_index(drop=True)

    all_features = []

    groups = df.groupby(["market_name", "commodity_name"])
    total_groups = len(groups)
    valid_groups = 0

    for (market, commodity), group in groups:
        if len(group) < MIN_OBSERVATIONS:
            continue

        features = _build_series_features(group.copy())
        if features is not None and not features.empty:
            all_features.append(features)
            valid_groups += 1

    logger.info(f"Generated features for {valid_groups}/{total_groups} market-commodity pairs")

    if not all_features:
        return pd.DataFrame()

    result = pd.concat(all_features, ignore_index=True)

    # Add exchange rate features
    fx_df = load_exchange_rates()
    if not fx_df.empty:
        result = _add_fx_features(result, fx_df)

    # Drop rows with NaN in core features (from lag calculations)
    # FX features are optional — don't require them
    core_feature_cols = [
        c for c in result.columns if c.startswith(("lag_", "roll_", "mom_", "cal_"))
    ]
    # Only require lag_30d and roll_mean_30d to be present (earlier lags will have data)
    required_cols = ["lag_30d", "roll_mean_30d"]
    available_required = [c for c in required_cols if c in result.columns]
    if available_required:
        result = result.dropna(subset=available_required)

    logger.info(f"Final feature table: {len(result)} rows, {len(core_feature_cols)} features")
    return result


def _build_series_features(group: pd.DataFrame) -> pd.DataFrame:
    """Build features for a single market-commodity time series.

    Args:
        group: DataFrame for one market-commodity pair, sorted by date.

    Returns:
        DataFrame with features added.
    """
    group = group.set_index("price_date").sort_index()

    # Ensure continuous date index (forward fill gaps up to 7 days)
    group = group.asfreq("D")
    group["price_ngn"] = group["price_ngn"].ffill(limit=7)
    group["market_name"] = group["market_name"].ffill()
    group["commodity_name"] = group["commodity_name"].ffill()
    group = group.dropna(subset=["price_ngn"])

    if len(group) < MIN_OBSERVATIONS:
        return None

    price = group["price_ngn"]

    # === Target variable ===
    # Predict price 7 days ahead
    group["target_7d"] = price.shift(-7)
    # Predict price 30 days ahead
    group["target_30d"] = price.shift(-30)

    # === Lag features ===
    for lag in [1, 3, 7, 14, 21, 30, 60, 90]:
        group[f"lag_{lag}d"] = price.shift(lag)

    # === Rolling statistics ===
    for window in [7, 14, 30, 60]:
        group[f"roll_mean_{window}d"] = price.rolling(window).mean()
        group[f"roll_std_{window}d"] = price.rolling(window).std()
        group[f"roll_min_{window}d"] = price.rolling(window).min()
        group[f"roll_max_{window}d"] = price.rolling(window).max()

    # === Momentum / Rate of change ===
    for window in [7, 14, 30]:
        group[f"mom_pct_change_{window}d"] = price.pct_change(window)

    # === Calendar features ===
    group["cal_month"] = group.index.month
    group["cal_quarter"] = group.index.quarter
    group["cal_day_of_week"] = group.index.dayofweek
    group["cal_day_of_year"] = group.index.dayofyear
    group["cal_week_of_year"] = group.index.isocalendar().week.astype(int)

    # === Seasonality indicators ===
    # Nigeria rainy season: April–October, Dry season: November–March
    month = group.index.month
    group["cal_is_rainy_season"] = ((month >= 4) & (month <= 10)).astype(int)
    # Lean season (pre-harvest food scarcity): June–August
    group["cal_is_lean_season"] = ((month >= 6) & (month <= 8)).astype(int)

    # Reset index
    group = group.reset_index().rename(columns={"index": "price_date"})

    return group


def _add_fx_features(df: pd.DataFrame, fx_df: pd.DataFrame) -> pd.DataFrame:
    """Add exchange rate features to the main DataFrame."""
    if fx_df.empty:
        return df

    # Merge on date (use nearest available rate)
    fx_df = fx_df.set_index("rate_date").sort_index()
    fx_df = fx_df.reindex(pd.date_range(fx_df.index.min(), fx_df.index.max(), freq="D"))
    fx_df["usd_ngn_rate"] = fx_df["usd_ngn_rate"].ffill()
    fx_df = fx_df.reset_index().rename(columns={"index": "price_date"})

    df = df.merge(
        fx_df[["price_date", "usd_ngn_rate"]].rename(columns={"usd_ngn_rate": "fx_usd_ngn"}),
        on="price_date",
        how="left",
    )

    # FX change features
    if "fx_usd_ngn" in df.columns:
        df["fx_usd_ngn"] = df["fx_usd_ngn"].ffill()
        df["fx_pct_change_7d"] = df.groupby(["market_name", "commodity_name"])[
            "fx_usd_ngn"
        ].pct_change(7)
        df["fx_pct_change_30d"] = df.groupby(["market_name", "commodity_name"])[
            "fx_usd_ngn"
        ].pct_change(30)

    return df


def save_features(df: pd.DataFrame) -> None:
    """Save feature table to database and CSV backup."""
    if df.empty:
        logger.warning("No features to save")
        return

    # Save to CSV
    output_dir = PROJECT_ROOT / "data" / "features"
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "ml_features.csv"
    df.to_csv(csv_path, index=False)
    logger.info(f"Saved features to {csv_path} ({len(df)} rows)")

    # Save to database
    engine = create_engine(get_database_url())
    # Write a summary table (full feature table is too wide for Postgres)
    summary = (
        df.groupby(["market_name", "commodity_name"])
        .agg(
            obs_count=("price_ngn", "count"),
            date_min=("price_date", "min"),
            date_max=("price_date", "max"),
            price_mean=("price_ngn", "mean"),
        )
        .reset_index()
    )

    summary.to_sql(
        "feature_summary",
        schema="ml",
        con=engine,
        if_exists="replace",
        index=False,
    )
    logger.info(f"Saved feature summary to ml.feature_summary ({len(summary)} pairs)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Load data
    prices = load_price_data()
    print(f"Loaded {len(prices)} observations")
    print(f"Commodities: {prices['commodity_name'].unique().tolist()}")
    print(f"Markets: {prices['market_name'].nunique()}")

    # Generate features
    features = generate_features(prices)

    if not features.empty:
        print(f"\nFeature table: {len(features)} rows")
        print(f"Columns: {len(features.columns)}")

        feature_cols = [
            c for c in features.columns if c.startswith(("lag_", "roll_", "mom_", "cal_", "fx_"))
        ]
        print(f"Feature columns ({len(feature_cols)}):")
        for col in sorted(feature_cols):
            print(f"  {col}")

        # Save
        save_features(features)
        print("\nFeatures saved successfully.")
    else:
        print("No features generated.")
