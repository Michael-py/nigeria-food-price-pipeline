"""World Bank Real-Time Prices (RTP) dataset client.

Fetches ML-estimated monthly food price data from the World Bank's
Development Economics Data Group via the Humanitarian Data Exchange (HDX).

This dataset covers 73+ Nigerian markets with data from 2007 to present,
updated weekly. It includes confidence scores and inflation estimates.

Data source: https://data.humdata.org/dataset/nigeria-real-time-prices
Catalog: https://microdata.worldbank.org/catalog/4503
"""

from __future__ import annotations

import io
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from sqlalchemy import create_engine

from ingestion.utils.config import get_database_url

logger = logging.getLogger(__name__)

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# HDX dataset ID for Nigeria Real-Time Prices
HDX_DATASET_ID = "nigeria-real-time-prices"
HDX_CKAN_URL = f"https://data.humdata.org/api/3/action/package_show?id={HDX_DATASET_ID}"

# Direct download URL (fallback — resolved from CKAN on 2026-07-21)
DIRECT_FOOD_PRICES_URL = (
    "https://data.humdata.org/dataset/73009422-8e57-41a4-ad24-d77f9405accb/"
    "resource/3b8a3d72-4229-4c35-99c1-8adfe6057c96/download/"
    "food-prices-for-nigeria.csv"
)

# Key commodities to extract (column names in the wide-format CSV)
# Each commodity has: price, o_ (observed flag), h_ (high), l_ (low),
# c_ (confidence), inflation_, trust_
TARGET_COMMODITIES = {
    "rice": "Rice",
    "rice_various": "Rice (various)",
    "maize": "Maize",
    "maize_flour": "Maize flour",
    "beans": "Beans",
    "cowpeas": "Cowpeas",
    "sorghum": "Sorghum",
    "millet": "Millet",
    "yam": "Yam",
    "cassava": "Cassava",
    "cassava_flour": "Cassava flour",
    "gari_fao": "Garri",
    "plantains": "Plantains",
    "oil": "Cooking oil",
    "groundnuts": "Groundnuts",
    "meat_beef": "Beef",
    "meat_chicken": "Chicken",
    "fish_catfish": "Catfish",
    "eggs": "Eggs",
    "tomatoes": "Tomatoes",
    "onions": "Onions",
    "sugar": "Sugar",
    "salt": "Salt",
    "wheat_flour": "Wheat flour",
    "milk": "Milk",
}


class WorldBankClient:
    """Client for fetching World Bank Real-Time Prices data from HDX."""

    def __init__(self) -> None:
        self.data_dir = PROJECT_ROOT / "data" / "downloads" / "worldbank"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "NigeriaFoodPricePipeline/0.1"})

    def fetch_prices(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Fetch Real-Time Prices data for Nigeria from HDX.

        Downloads the wide-format CSV, extracts target commodities,
        and melts into long format (one row per market-commodity-date).

        Args:
            start_date: Start of date range (filter after download).
            end_date: End of date range (filter after download).

        Returns:
            DataFrame with standardized columns:
                - price_date, market_name, commodity_name, price,
                  currency_name, unit_name, confidence_score, source
        """
        logger.info("Fetching World Bank Real-Time Prices for Nigeria from HDX...")

        # Step 1: Get the download URL (try CKAN API, fallback to direct URL)
        csv_url = self._get_food_prices_url()

        # Step 2: Download the CSV (with retry for slow connections)
        logger.info(f"Downloading from: {csv_url[:80]}...")
        df_wide = self._download_csv(csv_url)
        logger.info(
            f"Downloaded {len(df_wide)} rows, {len(df_wide.columns)} columns, "
            f"{df_wide['mkt_name'].nunique()} markets"
        )

        # Step 4: Melt from wide to long format
        df_long = self._melt_to_long_format(df_wide)

        # Step 5: Apply date filters
        if start_date:
            df_long = df_long[df_long["price_date"] >= pd.Timestamp(start_date)]
        if end_date:
            df_long = df_long[df_long["price_date"] <= pd.Timestamp(end_date)]

        # Step 6: Save backup
        backup_path = self.data_dir / "wb_rtp_nga_long.csv"
        df_long.to_csv(backup_path, index=False)
        logger.info(f"Saved backup to {backup_path} ({len(df_long)} rows)")

        # Also save raw wide-format for reference
        raw_path = self.data_dir / "wb_rtp_nga_raw.csv"
        df_wide.to_csv(raw_path, index=False)

        return df_long

    def _get_food_prices_url(self) -> str:
        """Get the current download URL for food prices CSV.

        Tries CKAN API first, falls back to hardcoded direct URL.
        """
        try:
            response = self.session.get(HDX_CKAN_URL, timeout=15)
            response.raise_for_status()
            pkg = response.json()["result"]
            for resource in pkg.get("resources", []):
                if (
                    "Food Prices" in resource.get("name", "")
                    and resource.get("format", "").upper() == "CSV"
                ):
                    url: str = resource["url"]
                    return url
        except Exception as e:
            logger.warning(f"CKAN API failed ({e}), using direct URL fallback")

        return DIRECT_FOOD_PRICES_URL

    def _download_csv(self, url: str, max_retries: int = 3) -> pd.DataFrame:
        """Download CSV with retry logic for slow/unstable connections.

        Args:
            url: URL to download.
            max_retries: Number of retry attempts.

        Returns:
            Parsed DataFrame.
        """
        import time

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, timeout=300, stream=False)
                response.raise_for_status()
                df = pd.read_csv(io.StringIO(response.text), low_memory=False)
                return df
            except (requests.RequestException, requests.ConnectionError) as e:
                if attempt == max_retries:
                    raise RuntimeError(
                        f"Failed to download after {max_retries} attempts: {e}"
                    ) from e
                wait = attempt * 10
                logger.warning(f"Download attempt {attempt} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)

        raise RuntimeError("Unreachable")

    def _melt_to_long_format(self, df_wide: pd.DataFrame) -> pd.DataFrame:
        """Convert wide-format RTP data to long format.

        The RTP CSV has one row per market-date with commodity prices as columns.
        We melt this into one row per market-date-commodity.

        Args:
            df_wide: Wide-format DataFrame from CSV.

        Returns:
            Long-format DataFrame with standardized columns.
        """
        # Identify metadata columns
        meta_cols = [
            "ISO3",
            "country",
            "adm1_name",
            "adm2_name",
            "mkt_name",
            "lat",
            "lon",
            "geo_id",
            "DATES",
            "year",
            "month",
            "currency",
            "components",
            "start_dense_data",
            "last_survey_point",
            "data_coverage",
            "data_coverage_recent",
            "index_confidence_score",
            "spatially_interpolated",
        ]
        meta_cols = [c for c in meta_cols if c in df_wide.columns]

        # Melt each target commodity
        all_records = []

        for col_name, display_name in TARGET_COMMODITIES.items():
            if col_name not in df_wide.columns:
                continue

            # Extract price and confidence columns for this commodity
            subset = df_wide[meta_cols + [col_name]].copy()
            subset = subset.rename(columns={col_name: "price"})
            subset["commodity_name"] = display_name

            # Get confidence score if available
            confidence_col = f"c_{col_name}"
            if confidence_col in df_wide.columns:
                subset["confidence_score"] = df_wide[confidence_col]
            else:
                subset["confidence_score"] = None

            # Drop rows where price is NaN
            subset = subset.dropna(subset=["price"])

            if not subset.empty:
                all_records.append(subset)

        if not all_records:
            logger.warning("No price data found for target commodities")
            return pd.DataFrame()

        # Combine all commodities
        df_long = pd.concat(all_records, ignore_index=True)

        # Standardize columns
        df_long = df_long.rename(
            columns={
                "DATES": "price_date",
                "mkt_name": "market_name",
                "currency": "currency_name",
                "adm1_name": "state",
            }
        )

        # Parse dates
        df_long["price_date"] = pd.to_datetime(df_long["price_date"]).dt.date

        # Add standard fields
        df_long["unit_name"] = "KG"  # RTP prices are per kg (local currency)
        df_long["source"] = "WorldBank_RTP"

        # Keep only needed columns
        keep_cols = [
            "price_date",
            "market_name",
            "commodity_name",
            "price",
            "currency_name",
            "unit_name",
            "state",
            "lat",
            "lon",
            "confidence_score",
            "source",
        ]
        df_long = df_long[[c for c in keep_cols if c in df_long.columns]]

        logger.info(
            f"Melted to {len(df_long)} rows | "
            f"{df_long['market_name'].nunique()} markets | "
            f"{df_long['commodity_name'].nunique()} commodities | "
            f"Date range: {df_long['price_date'].min()} to {df_long['price_date'].max()}"
        )

        return df_long

    def load_to_database(self, df: pd.DataFrame) -> int:
        """Load fetched data into raw.worldbank_prices table.

        Args:
            df: Long-format DataFrame from fetch_prices().

        Returns:
            Number of rows loaded.
        """
        if df.empty:
            logger.warning("No data to load — DataFrame is empty")
            return 0

        engine = create_engine(get_database_url())

        # Map to database schema
        db_df = df[["market_name", "commodity_name", "price", "price_date"]].copy()
        db_df["unit"] = df["unit_name"]
        db_df["country_code"] = "NGA"
        db_df["source"] = "WorldBank"

        db_df.to_sql(
            name="worldbank_prices",
            schema="raw",
            con=engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )

        row_count = len(db_df)
        logger.info(f"Loaded {row_count} rows into raw.worldbank_prices")
        return row_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = WorldBankClient()
    data = client.fetch_prices()
    print(f"\nFetched {len(data)} rows")
    print(f"Markets: {data['market_name'].nunique()}")
    print(f"Commodities: {data['commodity_name'].nunique()}")
    print(f"States: {data['state'].nunique()}")
    print(f"Date range: {data['price_date'].min()} to {data['price_date'].max()}")

    # Load into database
    loaded = client.load_to_database(data)
    print(f"\nLoaded {loaded} rows into raw.worldbank_prices")
