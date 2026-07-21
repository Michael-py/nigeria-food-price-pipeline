"""NBS Selected Food Prices Watch PDF extractor.

Extracts food price data from the National Bureau of Statistics monthly
"Selected Food Prices Watch" PDF reports.

Data source: https://www.nigerianstat.gov.ng/
"""

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from ingestion.utils.config import get_database_url

logger = logging.getLogger(__name__)

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class NBSExtractor:
    """Extracts food prices from NBS PDF reports."""

    def __init__(self) -> None:
        self.download_dir = PROJECT_ROOT / "data" / "downloads" / "nbs"
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def download_report(self, year: int, month: int) -> Path:
        """Download NBS Selected Food Prices Watch PDF.

        Args:
            year: Report year.
            month: Report month.

        Returns:
            Path to downloaded PDF file.
        """
        # TODO: Implement PDF download from NBS website
        logger.info(f"Downloading NBS report for {year}-{month:02d}...")
        raise NotImplementedError("Implement NBS PDF download in Week 2")

    def extract_prices(self, pdf_path: Path) -> pd.DataFrame:
        """Extract price data from NBS PDF report.

        Uses pdfplumber to parse tables from the PDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            DataFrame with columns: commodity_name, unit, price, report_month, state.
        """
        # TODO: Implement PDF table extraction with pdfplumber
        logger.info(f"Extracting prices from {pdf_path}...")
        raise NotImplementedError("Implement PDF extraction in Week 2")

    def load_to_database(self, df: pd.DataFrame) -> int:
        """Load extracted data into raw.nbs_prices table."""
        engine = create_engine(get_database_url())
        rows = df.to_sql(
            name="nbs_prices",
            schema="raw",
            con=engine,
            if_exists="append",
            index=False,
        )
        logger.info(f"Loaded {rows} rows into raw.nbs_prices")
        return rows or 0


if __name__ == "__main__":
    extractor = NBSExtractor()
    pdf = extractor.download_report(2026, 6)
    data = extractor.extract_prices(pdf)
    extractor.load_to_database(data)
