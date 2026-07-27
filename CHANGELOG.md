# Changelog

## v1.0.0 (2026-07-21)

### Initial Release

**Data Ingestion:**
- WFP food prices via HDX (87,963 rows, 68 markets, 43 commodities)
- World Bank Real-Time Prices via HDX (26,052 rows, 74 markets, 11 commodities)
- NBS Selected Food Prices via PDF extraction (413 rows, 6 zones, 45 commodities)
- CBN exchange rates via API
- Open-Meteo weather data via API

**Data Quality:**
- Great Expectations validation suites for all 5 raw tables
- Lightweight SQL validation module (17 checks)
- Unified validation runner with database logging

**Transformation (dbt):**
- 5 staging models with deduplication
- 1 intermediate unified price model
- 5 mart models (fct_daily_prices, fct_weekly_prices, fct_monthly_prices, dim_markets, dim_commodities)
- 14 dbt tests passing

**Machine Learning:**
- Feature engineering: 37 features (lags, rolling stats, momentum, calendar, seasonality)
- Baseline models: Naive, Moving Average, Seasonal Naive
- XGBoost models: 7-day and 30-day horizons, per-commodity
- MLflow experiment tracking and model registry
- Best result: Oil Palm 30d forecast — 36% MAPE improvement over naive

**Serving:**
- FastAPI REST API with /predict, /commodities, /markets, /prices/latest endpoints
- Streamlit dashboard with 4 pages (Trends, Comparison, Forecasts, Quality)
- OpenAPI documentation auto-generated

**Infrastructure:**
- Docker Compose with 7 services
- GitHub Actions CI (lint, format, type-check, test)
- Comprehensive documentation (architecture, API reference, setup guide, data dictionary)
