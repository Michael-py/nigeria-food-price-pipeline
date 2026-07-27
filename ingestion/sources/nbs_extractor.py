"""NBS Selected Food Prices Watch PDF extractor.

Extracts food price data from the National Bureau of Statistics monthly
"Selected Food Prices Watch" PDF reports.

Data sources:
- http://microdata.nigerianstat.gov.ng/index.php/catalog/162
- https://nigerianstat.gov.ng (direct downloads, often slow)

The PDFs contain:
- Executive summary with national averages (pages 3-4)
- Infographic pages (image-based, not extractable)
- Appendix tables (pages 15-16) with:
  - Zonal averages (6 geopolitical zones)
  - National averages with MoM/YoY changes and state-level highs/lows
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

import pandas as pd
import pdfplumber
import requests
from sqlalchemy import create_engine

from ingestion.utils.config import get_database_url

logger = logging.getLogger(__name__)

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Known report URLs (microdata.nigerianstat.gov.ng is more reliable)
# Pattern: catalog/162/download/{resource_id}
NBS_MICRODATA_BASE = "http://microdata.nigerianstat.gov.ng/index.php/catalog/162/download"

# Catalog page for auto-discovery of new reports
NBS_CATALOG_URL = "http://microdata.nigerianstat.gov.ng/index.php/catalog/162"

# Known resource IDs mapped to report months (auto-discovery supplements this)
KNOWN_REPORTS: dict[str, str] = {
    "2024-11": "1146",  # November 2024
    "2024-12": "1150",  # December 2024
    "2025-01": "1228",  # January 2025
    "2025-04": "1229",  # April 2025
}

# Geopolitical zones
ZONES = [
    "North Central",
    "North East",
    "North West",
    "South East",
    "South South",
    "South West",
]

# Zone column header variations found in PDFs
ZONE_HEADER_PATTERNS = [
    "NORTH CEN",
    "NORTH EAST",
    "NORTH WEST",
    "SOUTH EAST",
    "SOUTH SOUTH",
    "SOUTH WEST",
]


class NBSExtractor:
    """Extracts food prices from NBS Selected Food Prices Watch PDF reports.

    Strategy:
    1. Download PDF from microdata.nigerianstat.gov.ng
    2. Extract appendix pages (typically last 2-3 pages)
    3. Parse zonal average prices table
    4. Parse national summary table
    5. Return standardized DataFrame

    Usage:
        extractor = NBSExtractor()
        df = extractor.extract_from_report("2025-01")
        extractor.load_to_database(df)
    """

    def __init__(self) -> None:
        self.download_dir = PROJECT_ROOT / "data" / "downloads" / "nbs"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "NigeriaFoodPricePipeline/0.1"})

    def fetch_all_available(self) -> pd.DataFrame:
        """Fetch and extract data from all known report months.

        Tries to auto-discover new reports first, then processes all known ones.

        Returns:
            Combined DataFrame from all successfully extracted reports.
        """
        # Try to discover any new reports on the catalog page
        self._discover_new_reports()

        all_dfs = []
        for month_key, _resource_id in KNOWN_REPORTS.items():
            try:
                df = self.extract_from_report(month_key)
                if not df.empty:
                    all_dfs.append(df)
                    logger.info(f"Extracted {len(df)} rows from {month_key}")
            except Exception as e:
                logger.warning(f"Failed to extract {month_key}: {e}")

        if all_dfs:
            combined = pd.concat(all_dfs, ignore_index=True)
            logger.info(f"Total extracted: {len(combined)} rows from {len(all_dfs)} reports")
            return combined

        return pd.DataFrame()

    def _discover_new_reports(self) -> None:
        """Scrape the NBS microdata catalog page to find new report resources.

        Automatically adds any newly published reports to KNOWN_REPORTS.
        """
        try:
            response = self.session.get(NBS_CATALOG_URL, timeout=30)
            response.raise_for_status()
            html = response.text

            # Look for download links matching the pattern /download/{id}
            # and filenames containing month/year info
            import re

            # Find all download links
            links = re.findall(
                r'/catalog/162/download/(\d+)(?:/[^"]*?(?:([A-Z][a-z]+)(\d{2}))?)?',
                html,
            )

            month_map = {
                "Jan": "01",
                "Feb": "02",
                "Mar": "03",
                "Apr": "04",
                "May": "05",
                "Jun": "06",
                "Jul": "07",
                "Aug": "08",
                "Sep": "09",
                "Oct": "10",
                "Nov": "11",
                "Dec": "12",
            }

            for match in links:
                resource_id = match[0]
                month_abbr = match[1] if len(match) > 1 else ""
                year_short = match[2] if len(match) > 2 else ""

                if month_abbr in month_map and year_short:
                    year_full = f"20{year_short}"
                    month_num = month_map[month_abbr]
                    month_key = f"{year_full}-{month_num}"

                    if month_key not in KNOWN_REPORTS:
                        KNOWN_REPORTS[month_key] = resource_id
                        logger.info(f"Discovered new NBS report: {month_key} (ID: {resource_id})")

        except Exception as e:
            logger.warning(f"Auto-discovery failed (non-critical): {e}")

    def extract_from_report(self, month_key: str) -> pd.DataFrame:
        """Download and extract prices from a specific monthly report.

        Args:
            month_key: Month in "YYYY-MM" format (e.g., "2025-01").

        Returns:
            DataFrame with columns: commodity_name, price, zone, report_month, source.
        """
        # Download the PDF
        pdf_path = self.download_report(month_key)

        # Extract data from the PDF
        df = self.extract_prices(pdf_path, month_key)

        return df

    def download_report(self, month_key: str) -> Path:
        """Download NBS Selected Food Prices Watch PDF.

        Args:
            month_key: Month in "YYYY-MM" format.

        Returns:
            Path to downloaded PDF file.
        """
        if month_key not in KNOWN_REPORTS:
            raise ValueError(
                f"No known resource ID for {month_key}. Available: {list(KNOWN_REPORTS.keys())}"
            )

        resource_id = KNOWN_REPORTS[month_key]
        url = f"{NBS_MICRODATA_BASE}/{resource_id}"
        filename = f"Selected_Food_{month_key}.pdf"
        filepath = self.download_dir / filename

        # Use cached version if exists
        if filepath.exists() and filepath.stat().st_size > 100000:
            logger.info(f"Using cached: {filepath}")
            return filepath

        logger.info(f"Downloading NBS report for {month_key} from {url}...")
        response = self.session.get(url, timeout=120, allow_redirects=True)
        response.raise_for_status()

        filepath.write_bytes(response.content)
        logger.info(f"Saved: {filepath} ({len(response.content)} bytes)")

        return filepath

    def extract_prices(self, pdf_path: Path, month_key: str) -> pd.DataFrame:
        """Extract price data from NBS PDF report appendix tables.

        Focuses on the appendix pages which contain structured price tables
        with zonal and national averages.

        Args:
            pdf_path: Path to the PDF file.
            month_key: Month in "YYYY-MM" format (for the report_month column).

        Returns:
            DataFrame with columns: commodity_name, price, zone/state,
            report_month, unit, source.
        """
        logger.info(f"Extracting prices from {pdf_path.name}...")

        pdf = pdfplumber.open(str(pdf_path))
        all_records: list[dict] = []

        # Parse report month
        year, month = month_key.split("-")
        report_date = date(int(year), int(month), 1)

        # Scan all pages for appendix data
        for page in pdf.pages:
            text = page.extract_text() or ""
            if len(text) < 100:
                continue

            # Check if this is a zonal prices page
            if self._is_zonal_table(text):
                records = self._parse_zonal_table(text, report_date)
                all_records.extend(records)

            # Check if this is a national summary page
            elif self._is_national_summary(text):
                records = self._parse_national_summary(text, report_date)
                all_records.extend(records)

        pdf.close()

        if not all_records:
            logger.warning(f"No price data extracted from {pdf_path.name}")
            return pd.DataFrame()

        df = pd.DataFrame(all_records)

        # Save backup
        backup_path = self.download_dir / f"nbs_extracted_{month_key}.csv"
        df.to_csv(backup_path, index=False)

        logger.info(
            f"Extracted {len(df)} records | "
            f"{df['commodity_name'].nunique()} commodities | "
            f"{df['zone'].nunique()} zones"
        )

        return df

    def _is_zonal_table(self, text: str) -> bool:
        """Check if page text contains a zonal average price table."""
        # The zonal table has zone headers and "APPENDIX" or "Item Label"
        has_zones = sum(1 for z in ZONE_HEADER_PATTERNS if z in text.upper()) >= 3
        has_items = "Item Label" in text or "APPENDIX" in text
        return has_zones and has_items

    def _is_national_summary(self, text: str) -> bool:
        """Check if page text contains the national summary table."""
        has_mom = "MoM" in text or "Month-on-Month" in text.replace(" ", "")
        has_yoy = "YoY" in text or "Year-on-Year" in text.replace(" ", "")
        has_items = "Beans" in text or "Garri" in text or "Rice" in text
        return has_mom and has_yoy and has_items

    def _parse_zonal_table(self, text: str, report_date: date) -> list[dict]:
        """Parse the zonal average prices table from page text.

        The table format is typically:
        Item Label | NORTH CENTRAL | NORTH EAST | NORTH WEST | SOUTH EAST | SOUTH SOUTH | SOUTH WEST

        Args:
            text: Full page text.
            report_date: Date of the report.

        Returns:
            List of price records.
        """
        records: list[dict] = []
        lines = text.split("\n")

        for line in lines:
            # Skip header lines and short lines
            if "Item Label" in line or "NORTH" in line.upper() or len(line) < 20:
                continue
            if "APPENDIX" in line:
                continue

            # Try to parse: commodity_name followed by 6 numeric values
            # Pattern: "Beans Brown 2,580.80 2,434.87 1,836.71 2,999.59 2,690.45 2,382.22"
            prices = re.findall(r"[\d,]+\.\d{2}", line)

            if len(prices) >= 6:
                # Extract commodity name (everything before the first price)
                first_price_pos = line.find(prices[0])
                commodity_name = line[:first_price_pos].strip()

                if not commodity_name or commodity_name.isdigit():
                    continue

                # Map prices to zones
                for i, zone in enumerate(ZONES):
                    if i < len(prices):
                        try:
                            price_val = float(prices[i].replace(",", ""))
                            records.append(
                                {
                                    "commodity_name": commodity_name,
                                    "price": price_val,
                                    "zone": zone,
                                    "report_month": report_date.isoformat(),
                                    "currency_name": "NGN",
                                    "unit_name": "KG",
                                    "source": "NBS",
                                }
                            )
                        except ValueError:
                            continue

        logger.info(f"Parsed {len(records)} zonal price records")
        return records

    def _parse_national_summary(self, text: str, report_date: date) -> list[dict]:
        """Parse the national summary table with MoM/YoY data.

        Format varies but typically:
        Item Label | Previous Price | Current Price | MoM | YoY | Highest State | Lowest State

        We extract the current month's national average price.

        Args:
            text: Full page text.
            report_date: Date of the report.

        Returns:
            List of price records (national averages).
        """
        records: list[dict] = []
        lines = text.split("\n")

        for line in lines:
            # Skip headers
            if "Item Label" in line or "Average of" in line or len(line) < 20:
                continue

            # Look for lines with commodity names and multiple numbers
            prices = re.findall(r"[\d,]+\.\d{2}", line)

            if len(prices) >= 2:
                # Extract commodity name
                first_price_pos = line.find(prices[0])
                commodity_name = line[:first_price_pos].strip()

                if not commodity_name or commodity_name.isdigit():
                    continue

                # The pattern typically is: prev_month, current_month or
                # prev_year, prev_month, current_month
                # Take the last "reasonable" price as current month
                # (reasonable = between 100 and 50000 NGN)
                current_price = None
                for p in prices[:4]:  # Check first 4 numbers
                    val = float(p.replace(",", ""))
                    if 50 <= val <= 50000:
                        current_price = val

                if current_price:
                    records.append(
                        {
                            "commodity_name": commodity_name,
                            "price": current_price,
                            "zone": "National",
                            "report_month": report_date.isoformat(),
                            "currency_name": "NGN",
                            "unit_name": "KG",
                            "source": "NBS",
                        }
                    )

        logger.info(f"Parsed {len(records)} national summary records")
        return records

    def load_to_database(self, df: pd.DataFrame) -> int:
        """Load extracted data into raw.nbs_prices table.

        Args:
            df: DataFrame from extract methods.

        Returns:
            Number of rows loaded.
        """
        if df.empty:
            logger.warning("No data to load — DataFrame is empty")
            return 0

        engine = create_engine(get_database_url())

        db_df = df[["commodity_name", "unit_name", "price", "report_month"]].copy()
        db_df["state"] = df["zone"]
        db_df["source"] = "NBS"
        db_df = db_df.rename(columns={"unit_name": "unit"})

        db_df.to_sql(
            name="nbs_prices",
            schema="raw",
            con=engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )

        row_count = len(db_df)
        logger.info(f"Loaded {row_count} rows into raw.nbs_prices")
        return row_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    extractor = NBSExtractor()

    # Extract all available reports
    print("Extracting all available NBS reports...")
    df = extractor.fetch_all_available()

    if not df.empty:
        print(f"\nExtracted {len(df)} rows")
        print(f"Commodities: {df['commodity_name'].nunique()}")
        print(f"Zones: {df['zone'].unique().tolist()}")
        print(f"Months: {df['report_month'].unique().tolist()}")

        # Load into database
        loaded = extractor.load_to_database(df)
        print(f"\nLoaded {loaded} rows into raw.nbs_prices")
    else:
        print("No data extracted.")
