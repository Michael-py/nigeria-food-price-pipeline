"""CBN Exchange Rate data client.

Fetches daily exchange rate data from the Central Bank of Nigeria.

Data source: https://www.cbn.gov.ng/rates/ExchRateByCurrency.asp
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


class CBNClient:
    """Client for fetching CBN exchange rate data."""

    def __init__(self) -> None:
        self.data_dir = PROJECT_ROOT / "data" / "downloads" / "cbn"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def fetch_rates(
        self,
        start_date: "date | None" = None,
        end_date: "date | None" = None,
        currency: str = "USD",
    ) -> pd.DataFrame:
        """Fetch exchange rates from CBN.

        Args:
            start_date: Start of date range.
            end_date: End of date range.
            currency: Target currency (default USD).

        Returns:
            DataFrame with columns: rate_date, currency, buying_rate,
            central_rate, selling_rate.
        """
        # TODO: Implement CBN rate fetching
        logger.info(f"Fetching CBN {currency}/NGN rates...")
        raise NotImplementedError("Implement CBN rate fetch in Week 2")

    def load_to_database(self, df: pd.DataFrame) -> int:
        """Load fetched data into raw.cbn_rates table."""
        engine = create_engine(get_database_url())
        rows = df.to_sql(
            name="cbn_rates",
            schema="raw",
            con=engine,
            if_exists="append",
            index=False,
        )
        logger.info(f"Loaded {rows} rows into raw.cbn_rates")
        return rows or 0


if __name__ == "__main__":
    client = CBNClient()
    data = client.fetch_rates()
    client.load_to_database(data)
