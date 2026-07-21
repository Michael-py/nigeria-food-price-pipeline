"""WFP Food Price data client.

Supports two ingestion paths:
1. HDX CSV Download (default, no API key needed)
   - Downloads Nigeria food price CSV from Humanitarian Data Exchange
   - URL: https://data.humdata.org/dataset/wfp-food-prices-for-nigeria

2. DataBridges API (requires API key from WFP)
   - More granular, real-time data
   - Requires client_id/client_secret from wfp.vaminfo@wfp.org

The client automatically uses the API if WFP_API_KEY is set,
otherwise falls back to the HDX CSV download.
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

from ingestion.utils.config import get_database_url, get_env_var

logger = logging.getLogger(__name__)

# HDX direct download URL for Nigeria food prices (no auth required)
HDX_NIGERIA_CSV_URL = (
    "https://data.humdata.org/dataset/"
    "wfp-food-prices-for-nigeria/resource/"
    "download/wfp_food_prices_nga.csv"
)

# Fallback: HDX dataset page to scrape the latest resource URL
HDX_NIGERIA_DATASET_URL = "https://data.humdata.org/dataset/wfp-food-prices-for-nigeria"

# WFP DataBridges API endpoints
DATABRIDGES_TOKEN_URL = "https://api.wfp.org/token"
DATABRIDGES_PRICES_URL = "https://api.wfp.org/vam-food-prices/v1/MarketPrices"

# Nigeria country code
NIGERIA_ISO3 = "NGA"
NIGERIA_ADM0_CODE = 182  # WFP internal country code for Nigeria


class WFPClient:
    """Client for fetching food prices from WFP (HDX or DataBridges API).

    Usage:
        client = WFPClient()
        df = client.fetch_prices()
        client.load_to_database(df)
    """

    def __init__(self) -> None:
        self.api_key = get_env_var("WFP_API_KEY", "")
        self.api_secret = get_env_var("WFP_API_SECRET", "")
        self.data_dir = Path("data/downloads/wfp")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "NigeriaFoodPricePipeline/0.1"})

    @property
    def has_api_credentials(self) -> bool:
        """Check if DataBridges API credentials are configured."""
        return bool(self.api_key and self.api_secret)

    def fetch_prices(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Fetch food prices for Nigerian markets.

        Automatically chooses the best available data source:
        - If API credentials are set: uses DataBridges API
        - Otherwise: downloads from HDX (no auth needed)

        Args:
            start_date: Start of date range (inclusive). Only used with API path.
            end_date: End of date range (inclusive). Only used with API path.

        Returns:
            DataFrame with standardized columns:
                - market_name (str)
                - commodity_name (str)
                - currency_name (str)
                - unit_name (str)
                - price (float)
                - price_date (date)
        """
        if self.has_api_credentials:
            logger.info("WFP API credentials found — using DataBridges API")
            return self._fetch_from_api(start_date, end_date)
        else:
            logger.info("No WFP API key — using HDX CSV download (no auth needed)")
            return self._fetch_from_hdx(start_date, end_date)

    def _fetch_from_hdx(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Download and parse Nigeria food prices CSV from HDX.

        HDX provides a full historical CSV file that is updated regularly.
        No authentication required.

        Args:
            start_date: Filter results to this start date (post-download filter).
            end_date: Filter results to this end date (post-download filter).

        Returns:
            Standardized DataFrame of food prices.
        """
        logger.info("Downloading WFP Nigeria food prices from HDX...")

        # Try the direct resource URL first
        try:
            response = self.session.get(HDX_NIGERIA_CSV_URL, timeout=120)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"Direct HDX URL failed: {e}. Trying alternative...")
            # Alternative: try the CKAN API to get the latest resource URL
            response = self._fetch_hdx_via_ckan()

        # Parse CSV
        df = pd.read_csv(
            io.StringIO(response.text),
            parse_dates=["date"],
            low_memory=False,
        )

        logger.info(f"Downloaded {len(df)} raw rows from HDX")

        # Standardize column names (HDX CSV has specific column names)
        df = self._standardize_hdx_columns(df)

        # Apply date filters if provided
        if start_date:
            df = df[df["price_date"] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df["price_date"] <= pd.Timestamp(end_date)]

        # Save a local backup
        backup_path = self.data_dir / "wfp_nga_latest.csv"
        df.to_csv(backup_path, index=False)
        logger.info(f"Saved backup to {backup_path} ({len(df)} rows)")

        return df

    def _fetch_hdx_via_ckan(self) -> requests.Response:
        """Fetch data using HDX CKAN API to find the latest resource URL.

        HDX exposes a CKAN API that lets us look up the current download URL
        for the Nigeria food prices dataset.
        """
        ckan_url = (
            "https://data.humdata.org/api/3/action/package_show?id=wfp-food-prices-for-nigeria"
        )
        meta_response = self.session.get(ckan_url, timeout=30)
        meta_response.raise_for_status()

        package = meta_response.json()["result"]
        resources = package.get("resources", [])

        # Find the CSV resource
        csv_resource = None
        for resource in resources:
            if resource.get("format", "").upper() == "CSV":
                csv_resource = resource
                break

        if not csv_resource:
            raise RuntimeError("Could not find CSV resource in HDX dataset")

        download_url = csv_resource["url"]
        logger.info(f"Found HDX resource URL: {download_url}")

        response = self.session.get(download_url, timeout=120)
        response.raise_for_status()
        return response

    def _standardize_hdx_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize HDX CSV columns to our internal schema.

        HDX WFP food prices CSV typically has columns:
            date, admin1, admin2, market, latitude, longitude,
            category, commodity, unit, priceflag, pricetype, currency, price, usdprice

        We map these to our standard schema.
        """
        # Rename columns to our standard
        column_mapping = {
            "date": "price_date",
            "market": "market_name",
            "commodity": "commodity_name",
            "currency": "currency_name",
            "unit": "unit_name",
            "price": "price",
        }

        # Only rename columns that exist
        rename_map = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=rename_map)

        # Keep only the columns we need (plus useful metadata)
        keep_cols = [
            "price_date",
            "market_name",
            "commodity_name",
            "currency_name",
            "unit_name",
            "price",
        ]

        # Add optional columns if present
        optional_cols = ["admin1", "admin2", "latitude", "longitude", "category"]
        for col in optional_cols:
            if col in df.columns:
                keep_cols.append(col)

        df = df[[c for c in keep_cols if c in df.columns]].copy()

        # Clean up
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df = df.dropna(subset=["price", "price_date", "market_name", "commodity_name"])
        df["price_date"] = pd.to_datetime(df["price_date"]).dt.date

        # Add source identifier
        df["source"] = "WFP_HDX"

        logger.info(
            f"Standardized to {len(df)} rows | "
            f"{df['market_name'].nunique()} markets | "
            f"{df['commodity_name'].nunique()} commodities | "
            f"Date range: {df['price_date'].min()} to {df['price_date'].max()}"
        )

        return df

    def _fetch_from_api(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Fetch prices from WFP DataBridges API (requires credentials).

        Uses OAuth2 client_credentials flow to get an access token,
        then queries the MarketPrices endpoint for Nigeria.

        Args:
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            Standardized DataFrame of food prices.
        """
        # Step 1: Get access token via OAuth2 client credentials
        token = self._get_api_token()

        # Step 2: Query market prices for Nigeria
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "CountryCode": NIGERIA_ISO3,
            "format": "json",
        }
        if start_date:
            params["startDate"] = start_date.isoformat()
        if end_date:
            params["endDate"] = end_date.isoformat()

        logger.info("Querying DataBridges API for Nigeria prices...")

        all_items = []
        page = 1

        while True:
            params["page"] = page
            response = self.session.get(
                DATABRIDGES_PRICES_URL,
                headers=headers,
                params=params,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            if not items:
                break

            all_items.extend(items)
            page += 1

            # Respect rate limits
            total_pages = data.get("totalPages", 1)
            if page > total_pages:
                break

        logger.info(f"Fetched {len(all_items)} price records from DataBridges API")

        if not all_items:
            return pd.DataFrame()

        # Convert to DataFrame and standardize
        df = pd.DataFrame(all_items)
        df = self._standardize_api_columns(df)

        return df

    def _get_api_token(self) -> str:
        """Get OAuth2 access token from WFP DataBridges.

        Uses client_credentials grant type.
        """
        response = self.session.post(
            DATABRIDGES_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.api_secret,
            },
            timeout=30,
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        logger.info("Successfully obtained WFP API access token")
        return token

    def _standardize_api_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize DataBridges API response to our internal schema."""
        column_mapping = {
            "marketName": "market_name",
            "commodityName": "commodity_name",
            "currencyName": "currency_name",
            "unitName": "unit_name",
            "commodityPrice": "price",
            "commodityPriceDate": "price_date",
        }

        rename_map = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=rename_map)

        # Parse dates and clean
        df["price_date"] = pd.to_datetime(df["price_date"]).dt.date
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df = df.dropna(subset=["price", "price_date", "market_name", "commodity_name"])

        # Add source identifier
        df["source"] = "WFP_API"

        # Keep standard columns
        keep_cols = [
            "price_date",
            "market_name",
            "commodity_name",
            "currency_name",
            "unit_name",
            "price",
            "source",
        ]
        df = df[[c for c in keep_cols if c in df.columns]].copy()

        return df

    def load_to_database(self, df: pd.DataFrame) -> int:
        """Load fetched data into raw.wfp_prices table.

        Args:
            df: DataFrame from fetch_prices().

        Returns:
            Number of rows inserted.
        """
        if df.empty:
            logger.warning("No data to load — DataFrame is empty")
            return 0

        engine = create_engine(get_database_url())

        # Map our standard columns to the database table columns
        db_df = df[
            ["market_name", "commodity_name", "currency_name", "unit_name", "price", "price_date"]
        ].copy()
        db_df["country_name"] = "Nigeria"
        db_df["source"] = df.get("source", "WFP")

        db_df.to_sql(
            name="wfp_prices",
            schema="raw",
            con=engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )

        row_count = len(db_df)
        logger.info(f"Loaded {row_count} rows into raw.wfp_prices")
        return row_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = WFPClient()
    data = client.fetch_prices()
    print(f"\nFetched {len(data)} rows")
    print(f"Markets: {data['market_name'].nunique()}")
    print(f"Commodities: {data['commodity_name'].nunique()}")
    print(f"Date range: {data['price_date'].min()} to {data['price_date'].max()}")
    print(f"\nSample:\n{data.head()}")

    # Uncomment to load into database:
    # client.load_to_database(data)
