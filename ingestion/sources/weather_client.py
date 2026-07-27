"""Open-Meteo Weather API client.

Fetches historical and forecast weather data for Nigerian market locations.
Weather features (rainfall, temperature) are used as predictors for food prices.

Data source: https://open-meteo.com/
API docs: https://open-meteo.com/en/docs/historical-weather-api
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from sqlalchemy import create_engine

from ingestion.utils.config import get_database_url, get_env_var

logger = logging.getLogger(__name__)

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Key Nigerian market coordinates (latitude, longitude)
NIGERIAN_MARKETS = {
    "Lagos (Mile 12)": (6.5833, 3.3833),
    "Kano (Dawanau)": (12.0022, 8.5920),
    "Abuja (Wuse)": (9.0579, 7.4951),
    "Port Harcourt": (4.8156, 7.0498),
    "Ibadan (Bodija)": (7.4106, 3.9055),
    "Kaduna": (10.5105, 7.4165),
    "Maiduguri": (11.8311, 13.1510),
    "Enugu": (6.4584, 7.5464),
    "Jos": (9.8965, 8.8583),
    "Sokoto": (13.0059, 5.2476),
}


class WeatherClient:
    """Client for fetching weather data from Open-Meteo API.

    Open-Meteo is free for non-commercial use, requires no API key,
    and provides historical weather data globally.
    """

    def __init__(self) -> None:
        self.base_url = get_env_var("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1")
        self.data_dir = PROJECT_ROOT / "data" / "downloads" / "weather"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "NigeriaFoodPricePipeline/0.1"})

    def fetch_weather(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        markets: Optional[dict[str, tuple[float, float]]] = None,
    ) -> pd.DataFrame:
        """Fetch weather data for Nigerian market locations.

        Args:
            start_date: Start of date range. Defaults to 2 years ago.
            end_date: End of date range. Defaults to yesterday.
            markets: Dict of market_name -> (latitude, longitude).
                     Defaults to NIGERIAN_MARKETS.

        Returns:
            DataFrame with columns: market_name, latitude, longitude,
            weather_date, temperature_max, temperature_min,
            precipitation_mm, humidity_pct.
        """
        if markets is None:
            markets = NIGERIAN_MARKETS
        if start_date is None:
            start_date = date.today() - timedelta(days=730)
        if end_date is None:
            end_date = date.today() - timedelta(days=1)

        logger.info(
            f"Fetching weather data for {len(markets)} markets from {start_date} to {end_date}..."
        )

        all_records = []

        for market_name, (lat, lon) in markets.items():
            try:
                market_df = self._fetch_market_weather(market_name, lat, lon, start_date, end_date)
                all_records.append(market_df)
                logger.info(f"  {market_name}: {len(market_df)} days")
            except Exception as e:
                logger.warning(f"  {market_name}: failed - {e}")

        if not all_records:
            logger.warning("No weather data fetched for any market")
            return pd.DataFrame()

        df = pd.concat(all_records, ignore_index=True)

        # Save backup
        backup_path = self.data_dir / "weather_latest.csv"
        df.to_csv(backup_path, index=False)
        logger.info(
            f"Fetched {len(df)} total weather records | "
            f"{df['market_name'].nunique()} markets | "
            f"Range: {df['weather_date'].min()} to {df['weather_date'].max()}"
        )

        return df

    def _fetch_market_weather(
        self, market_name: str, lat: float, lon: float, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Fetch weather data for a single market location from Open-Meteo.

        Open-Meteo endpoints:
        - /v1/forecast: works for past ~92 days + 16 day forecast
        - /v1/archive: works for historical data (older than ~3 months)

        We split the request if the range spans both.
        """
        results = []

        # Determine cutoff: archive handles everything older than 92 days ago
        archive_cutoff = date.today() - timedelta(days=92)

        # Part 1: Historical data via archive (if start_date is old enough)
        if start_date < archive_cutoff:
            archive_end = min(end_date, archive_cutoff - timedelta(days=1))
            try:
                df = self._call_api("archive", lat, lon, start_date, archive_end)
                if not df.empty:
                    results.append(df)
            except Exception:
                pass  # Archive might not cover all locations

        # Part 2: Recent data via forecast with past_days
        forecast_start = max(start_date, archive_cutoff)
        if forecast_start <= end_date:
            try:
                df = self._call_api("forecast", lat, lon, forecast_start, end_date)
                if not df.empty:
                    results.append(df)
            except Exception:
                pass

        if not results:
            return pd.DataFrame()

        df = pd.concat(results, ignore_index=True)
        df["market_name"] = market_name
        df["latitude"] = lat
        df["longitude"] = lon
        return df

    def _call_api(
        self, endpoint: str, lat: float, lon: float, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Call Open-Meteo API (archive or forecast)."""
        url = f"{self.base_url}/{endpoint}"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,relative_humidity_2m_mean",
            "timezone": "Africa/Lagos",
        }

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        daily = data.get("daily", {})
        if not daily or not daily.get("time"):
            return pd.DataFrame()

        df = pd.DataFrame(
            {
                "weather_date": daily["time"],
                "temperature_max": daily.get("temperature_2m_max"),
                "temperature_min": daily.get("temperature_2m_min"),
                "precipitation_mm": daily.get("precipitation_sum"),
                "humidity_pct": daily.get("relative_humidity_2m_mean"),
            }
        )
        df["weather_date"] = pd.to_datetime(df["weather_date"]).dt.date
        return df

    def load_to_database(self, df: pd.DataFrame) -> int:
        """Load fetched data into raw.weather table."""
        if df.empty:
            logger.warning("No data to load — DataFrame is empty")
            return 0

        engine = create_engine(get_database_url())
        db_df = df[
            [
                "market_name",
                "latitude",
                "longitude",
                "weather_date",
                "temperature_max",
                "temperature_min",
                "precipitation_mm",
                "humidity_pct",
            ]
        ].copy()
        db_df["source"] = "OpenMeteo"

        db_df.to_sql(
            name="weather",
            schema="raw",
            con=engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )

        row_count = len(db_df)
        logger.info(f"Loaded {row_count} rows into raw.weather")
        return row_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = WeatherClient()
    # Fetch last 6 months for testing
    data = client.fetch_weather(
        start_date=date.today() - timedelta(days=180),
    )
    if not data.empty:
        print(f"\nFetched {len(data)} rows")
        print(f"Markets: {data['market_name'].nunique()}")
        print(f"Date range: {data['weather_date'].min()} to {data['weather_date'].max()}")

        loaded = client.load_to_database(data)
        print(f"Loaded {loaded} rows into raw.weather")
