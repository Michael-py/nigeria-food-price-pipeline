"""Configuration utilities for the pipeline."""

import os

from dotenv import load_dotenv

load_dotenv()


def get_env_var(key: str, default: str = "") -> str:
    """Get environment variable with optional default."""
    return os.getenv(key, default)


def get_database_url() -> str:
    """Construct PostgreSQL database URL from environment variables."""
    host = get_env_var("POSTGRES_HOST", "localhost")
    port = get_env_var("POSTGRES_PORT", "5432")
    db = get_env_var("POSTGRES_DB", "food_prices")
    user = get_env_var("POSTGRES_USER", "pipeline")
    password = get_env_var("POSTGRES_PASSWORD", "changeme")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
