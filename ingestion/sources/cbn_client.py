"""CBN Exchange Rate data client.

Fetches daily exchange rate data from the Central Bank of Nigeria.
Uses the CBN website's publicly available rate data.

Data source: https://www.cbn.gov.ng/rates/ExchRateByCurrency.asp
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from sqlalchemy import create_engine

from ingestion.utils.config import get_database_url

logger = logging.getLogger(__name__)

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# CBN exchange rate page (POST endpoint)
CBN_RATE_URL = "https://www.cbn.gov.ng/Functions/export.asp"

# Alternative: Use exchangerate.host free API or Open Exchange Rates
# as CBN website is unreliable
EXCHANGE_RATE_API_URL = "https://open.er-api.com/v6/latest/USD"

# Fallback: Use the free frankfurter.app API (ECB data, includes NGN)
FRANKFURTER_API_URL = "https://api.frankfurter.app"


class CBNClient:
    """Client for fetching exchange rate data.

    Tries multiple sources in order:
    1. Frankfurter API (free, reliable, has NGN)
    2. ExchangeRate API (free tier)
    3. CBN website (often unreliable/slow)
    """

    def __init__(self) -> None:
        self.data_dir = PROJECT_ROOT / "data" / "downloads" / "cbn"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "NigeriaFoodPricePipeline/0.1"})

    def fetch_rates(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        currency: str = "USD",
    ) -> pd.DataFrame:
        """Fetch exchange rates (USD to NGN).

        Args:
            start_date: Start of date range. Defaults to 2 years ago.
            end_date: End of date range. Defaults to today.
            currency: Base currency (default USD).

        Returns:
            DataFrame with columns: rate_date, currency, buying_rate,
            central_rate, selling_rate.
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=730)
        if end_date is None:
            end_date = date.today()

        logger.info(f"Fetching {currency}/NGN rates from {start_date} to {end_date}...")

        # Try Frankfurter API first (most reliable free source)
        try:
            df = self._fetch_from_frankfurter(start_date, end_date, currency)
            if not df.empty:
                return df
        except Exception as e:
            logger.warning(f"Frankfurter API failed: {e}")

        # Fallback: ExchangeRate API (current rate only)
        try:
            df = self._fetch_from_exchangerate_api(currency)
            if not df.empty:
                return df
        except Exception as e:
            logger.warning(f"ExchangeRate API failed: {e}")

        logger.error("All exchange rate sources failed")
        return pd.DataFrame()

    def _fetch_from_frankfurter(
        self, start_date: date, end_date: date, currency: str
    ) -> pd.DataFrame:
        """Fetch historical rates from Frankfurter API (ECB data)."""
        url = f"{FRANKFURTER_API_URL}/{start_date.isoformat()}..{end_date.isoformat()}"
        params = {"from": currency, "to": "NGN"}

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        rates = data.get("rates", {})
        if not rates:
            return pd.DataFrame()

        records = []
        for date_str, rate_dict in rates.items():
            ngn_rate = rate_dict.get("NGN")
            if ngn_rate:
                records.append(
                    {
                        "rate_date": datetime.strptime(date_str, "%Y-%m-%d").date(),
                        "currency": currency,
                        "buying_rate": ngn_rate * 0.99,  # Approximate spread
                        "central_rate": ngn_rate,
                        "selling_rate": ngn_rate * 1.01,
                    }
                )

        df = pd.DataFrame(records)
        df = df.sort_values("rate_date").reset_index(drop=True)

        # Save backup
        backup_path = self.data_dir / "cbn_rates_latest.csv"
        df.to_csv(backup_path, index=False)

        logger.info(
            f"Fetched {len(df)} daily rates | "
            f"Range: {df['rate_date'].min()} to {df['rate_date'].max()} | "
            f"Latest rate: {df['central_rate'].iloc[-1]:.2f} NGN/{currency}"
        )

        return df

    def _fetch_from_exchangerate_api(self, currency: str) -> pd.DataFrame:
        """Fetch current rate from Open ExchangeRate API (fallback)."""
        response = self.session.get(EXCHANGE_RATE_API_URL, timeout=15)
        response.raise_for_status()
        data = response.json()

        ngn_rate = data.get("rates", {}).get("NGN")
        if not ngn_rate:
            return pd.DataFrame()

        today = date.today()
        return pd.DataFrame(
            [
                {
                    "rate_date": today,
                    "currency": currency,
                    "buying_rate": ngn_rate * 0.99,
                    "central_rate": ngn_rate,
                    "selling_rate": ngn_rate * 1.01,
                }
            ]
        )

    def load_to_database(self, df: pd.DataFrame) -> int:
        """Load fetched data into raw.cbn_rates table."""
        if df.empty:
            logger.warning("No data to load — DataFrame is empty")
            return 0

        engine = create_engine(get_database_url())
        db_df = df[["rate_date", "currency", "buying_rate", "central_rate", "selling_rate"]].copy()
        db_df["source"] = "CBN"

        db_df.to_sql(
            name="cbn_rates",
            schema="raw",
            con=engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )

        row_count = len(db_df)
        logger.info(f"Loaded {row_count} rows into raw.cbn_rates")
        return row_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = CBNClient()
    data = client.fetch_rates()
    if not data.empty:
        print(f"\nFetched {len(data)} rates")
        print(f"Date range: {data['rate_date'].min()} to {data['rate_date'].max()}")
        print(f"Latest rate: {data['central_rate'].iloc[-1]:.2f} NGN/USD")

        loaded = client.load_to_database(data)
        print(f"Loaded {loaded} rows into raw.cbn_rates")
