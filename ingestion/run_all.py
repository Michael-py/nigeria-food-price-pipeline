"""Run all data ingestion sources and load into the PostgreSQL raw schema.

Usage:
    python -m ingestion.run_all

This script:
1. Fetches WFP food prices from HDX → raw.wfp_prices
2. Fetches World Bank RTP prices from HDX → raw.worldbank_prices
3. Extracts NBS prices from PDF reports → raw.nbs_prices

All data lands in the 'raw' schema of the food_prices database.
Requires PostgreSQL to be running (docker compose up postgres).
"""

from __future__ import annotations

import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def ingest_wfp() -> int:
    """Ingest WFP food prices from HDX."""
    from ingestion.sources.wfp_client import WFPClient

    logger.info("=" * 60)
    logger.info("SOURCE: WFP Food Prices (HDX)")
    logger.info("=" * 60)

    client = WFPClient()
    data = client.fetch_prices()

    if data.empty:
        logger.warning("WFP: No data fetched")
        return 0

    logger.info(f"WFP: Fetched {len(data)} rows, {data['market_name'].nunique()} markets")
    loaded = client.load_to_database(data)
    logger.info(f"WFP: Loaded {loaded} rows into raw.wfp_prices")
    return loaded


def ingest_worldbank() -> int:
    """Ingest World Bank Real-Time Prices from HDX."""
    from ingestion.sources.worldbank_client import WorldBankClient

    logger.info("=" * 60)
    logger.info("SOURCE: World Bank Real-Time Prices (HDX)")
    logger.info("=" * 60)

    client = WorldBankClient()
    data = client.fetch_prices()

    if data.empty:
        logger.warning("WorldBank: No data fetched")
        return 0

    logger.info(
        f"WorldBank: Fetched {len(data)} rows, "
        f"{data['market_name'].nunique()} markets, "
        f"{data['commodity_name'].nunique()} commodities"
    )
    loaded = client.load_to_database(data)
    logger.info(f"WorldBank: Loaded {loaded} rows into raw.worldbank_prices")
    return loaded


def ingest_nbs() -> int:
    """Ingest NBS Selected Food Prices from PDF reports."""
    from ingestion.sources.nbs_extractor import NBSExtractor

    logger.info("=" * 60)
    logger.info("SOURCE: NBS Selected Food Prices Watch (PDF)")
    logger.info("=" * 60)

    extractor = NBSExtractor()
    data = extractor.fetch_all_available()

    if data.empty:
        logger.warning("NBS: No data extracted")
        return 0

    logger.info(
        f"NBS: Extracted {len(data)} rows, "
        f"{data['commodity_name'].nunique()} commodities, "
        f"{data['zone'].nunique()} zones"
    )
    loaded = extractor.load_to_database(data)
    logger.info(f"NBS: Loaded {loaded} rows into raw.nbs_prices")
    return loaded


def ingest_cbn() -> int:
    """Ingest CBN exchange rates."""
    from ingestion.sources.cbn_client import CBNClient

    logger.info("=" * 60)
    logger.info("SOURCE: CBN Exchange Rates")
    logger.info("=" * 60)

    client = CBNClient()
    data = client.fetch_rates()

    if data.empty:
        logger.warning("CBN: No data fetched")
        return 0

    logger.info(f"CBN: Fetched {len(data)} daily rates")
    loaded = client.load_to_database(data)
    logger.info(f"CBN: Loaded {loaded} rows into raw.cbn_rates")
    return loaded


def ingest_weather() -> int:
    """Ingest weather data from Open-Meteo."""
    from datetime import timedelta

    from ingestion.sources.weather_client import WeatherClient

    logger.info("=" * 60)
    logger.info("SOURCE: Open-Meteo Weather Data")
    logger.info("=" * 60)

    client = WeatherClient()
    # Fetch last 2 years of weather data
    from datetime import date as date_type

    data = client.fetch_weather(
        start_date=date_type.today() - timedelta(days=730),
    )

    if data.empty:
        logger.warning("Weather: No data fetched")
        return 0

    logger.info(f"Weather: Fetched {len(data)} records, {data['market_name'].nunique()} markets")
    loaded = client.load_to_database(data)
    logger.info(f"Weather: Loaded {loaded} rows into raw.weather")
    return loaded


def main() -> None:
    """Run all ingestion sources."""
    logger.info("Starting full ingestion pipeline...")
    start_time = time.time()

    results = {}

    # WFP
    try:
        results["wfp"] = ingest_wfp()
    except Exception as e:
        logger.error(f"WFP ingestion failed: {e}")
        results["wfp"] = 0

    # World Bank
    try:
        results["worldbank"] = ingest_worldbank()
    except Exception as e:
        logger.error(f"World Bank ingestion failed: {e}")
        results["worldbank"] = 0

    # NBS
    try:
        results["nbs"] = ingest_nbs()
    except Exception as e:
        logger.error(f"NBS ingestion failed: {e}")
        results["nbs"] = 0

    # CBN Exchange Rates
    try:
        results["cbn"] = ingest_cbn()
    except Exception as e:
        logger.error(f"CBN ingestion failed: {e}")
        results["cbn"] = 0

    # Weather
    try:
        results["weather"] = ingest_weather()
    except Exception as e:
        logger.error(f"Weather ingestion failed: {e}")
        results["weather"] = 0

    # Summary
    elapsed = time.time() - start_time
    total_rows = sum(results.values())

    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"WFP:       {results['wfp']:>10,} rows")
    logger.info(f"WorldBank: {results['worldbank']:>10,} rows")
    logger.info(f"NBS:       {results['nbs']:>10,} rows")
    logger.info(f"CBN:       {results['cbn']:>10,} rows")
    logger.info(f"Weather:   {results['weather']:>10,} rows")
    logger.info(f"{'─' * 30}")
    logger.info(f"Total:     {total_rows:>10,} rows")
    logger.info(f"Duration:  {elapsed:.1f}s")

    if total_rows == 0:
        logger.error("No data loaded. Check database connection and source availability.")
        sys.exit(1)


if __name__ == "__main__":
    main()
