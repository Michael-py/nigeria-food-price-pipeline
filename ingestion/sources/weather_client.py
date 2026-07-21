"""Open-Meteo Weather API client.

Fetches historical and forecast weather data for Nigerian market locations.
Weather features (rainfall, temperature) are used as predictors for food prices.

Data source: https://open-meteo.com/
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import requests  # noqa: F401 — used when fetch_weather is implemented
from sqlalchemy import create_engine

from ingestion.utils.config import get_database_url, get_env_var

logger = logging.getLogger(__name__)

# Key Nigerian market coordinates
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


# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class WeatherClient:
    """Client for fetching weather data from Open-Meteo API."""

    def __init__(self) -> None:
        self.base_url = get_env_var("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1")
        self.data_dir = PROJECT_ROOT / "data" / "downloads" / "weather"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def fetch_weather(
        self,
        start_date: date,
        end_date: date,
        markets: Optional[dict[str, tuple[float, float]]] = None,
    ) -> pd.DataFrame:
        """Fetch weather data for Nigerian market locations.

        Args:
            start_date: Start of date range.
            end_date: End of date range.
            markets: Dict of market_name -> (latitude, longitude).
                     Defaults to NIGERIAN_MARKETS.

        Returns:
            DataFrame with columns: market_name, latitude, longitude,
            weather_date, temperature_max, temperature_min,
            precipitation_mm, humidity_pct.
        """
        if markets is None:
            markets = NIGERIAN_MARKETS

        # TODO: Implement Open-Meteo API call for each market location
        logger.info(f"Fetching weather data for {len(markets)} markets...")
        raise NotImplementedError("Implement weather fetch in Week 2")

    def load_to_database(self, df: pd.DataFrame) -> int:
        """Load fetched data into raw.weather table."""
        engine = create_engine(get_database_url())
        rows = df.to_sql(
            name="weather",
            schema="raw",
            con=engine,
            if_exists="append",
            index=False,
        )
        logger.info(f"Loaded {rows} rows into raw.weather")
        return rows or 0


if __name__ == "__main__":
    client = WeatherClient()
    data = client.fetch_weather(
        start_date=date(2024, 1, 1),
        end_date=date(2026, 7, 1),
    )
    client.load_to_database(data)
