"""World Bank Real-Time Prices (RTP) dataset client.

Fetches ML-estimated weekly food price data from the World Bank's
Development Economics Data Group.

Data source: https://microdata.worldbank.org/index.php/catalog/4503
"""

import logging
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from ingestion.utils.config import get_database_url

logger = logging.getLogger(__name__)

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class WorldBankClient:
    """Client for fetching World Bank Real-Time Prices data."""

    def __init__(self) -> None:
        self.data_dir = PROJECT_ROOT / "data" / "downloads" / "worldbank"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def fetch_prices(
        self,
        start_date: "date | None" = None,
        end_date: "date | None" = None,
    ) -> pd.DataFrame:
        """Fetch Real-Time Prices data for Nigeria.

        The RTP dataset provides weekly ML-estimated food prices for
        Nigerian markets and commodities.

        Args:
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            DataFrame with columns: country_code, market_name, commodity_name,
            unit, price, price_date.
        """
        # TODO: Implement World Bank RTP data download
        logger.info("Fetching World Bank Real-Time Prices for Nigeria...")
        raise NotImplementedError("Implement World Bank fetch in Week 2")

    def load_to_database(self, df: pd.DataFrame) -> int:
        """Load fetched data into raw.worldbank_prices table."""
        engine = create_engine(get_database_url())
        rows = df.to_sql(
            name="worldbank_prices",
            schema="raw",
            con=engine,
            if_exists="append",
            index=False,
        )
        logger.info(f"Loaded {rows} rows into raw.worldbank_prices")
        return rows or 0


if __name__ == "__main__":
    client = WorldBankClient()
    data = client.fetch_prices()
    client.load_to_database(data)
