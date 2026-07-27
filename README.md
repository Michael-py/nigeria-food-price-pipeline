# 🇳🇬 Nigeria Food Price Intelligence Pipeline

> An end-to-end data engineering and machine learning platform for real-time food price monitoring and forecasting across Nigerian commodity markets.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](https://docs.docker.com/compose/)

---

## Problem Statement

Nigeria's food inflation exceeded 40% year-on-year in early 2025, making food affordability the country's most pressing economic challenge. Despite this, food price data remains:

- **Delayed:** NBS publishes monthly with 3–4 week lag
- **Fragmented:** Data scattered across WFP, NBS, World Bank, and market-level sources
- **Inaccessible:** No public API or dashboard serves stakeholders in real time
- **Unactionable:** No forecasting layer exists to predict price movements

This project fills that gap with a fully automated, open-source data platform.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATION (Airflow)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐   ┌──────────────┐   ┌─────────────┐              │
│  │  INGEST  │──▶│   VALIDATE   │──▶│  TRANSFORM  │              │
│  │          │   │              │   │             │              │
│  │ - WFP    │   │ Great        │   │ dbt Core    │              │
│  │ - NBS    │   │ Expectations │   │ (staging →  │              │
│  │ - World  │   │              │   │  marts)     │              │
│  │   Bank   │   └──────────────┘   └──────┬──────┘              │
│  │ - CBN    │                              │                     │
│  │ - Weather│                              ▼                     │
│  └──────────┘                     ┌─────────────┐               │
│                                   │   STORAGE   │               │
│                                   │ PostgreSQL  │               │
│                                   └──────┬──────┘               │
│                                          │                       │
│                    ┌─────────────────────┼──────────────────┐    │
│                    │                     │                  │    │
│                    ▼                     ▼                  ▼    │
│           ┌──────────────┐    ┌──────────────┐   ┌───────────┐  │
│           │   ML TRAIN   │    │   ML SERVE   │   │ DASHBOARD │  │
│           │              │    │              │   │           │  │
│           │ MLflow +     │    │ FastAPI      │   │ Streamlit │  │
│           │ XGBoost      │    │ /predict     │   │           │  │
│           └──────────────┘    └──────────────┘   └───────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| Orchestration | Apache Airflow | Schedule and monitor data pipelines |
| Ingestion | Python (requests, BeautifulSoup) | Pull data from APIs and web sources |
| Data Quality | Great Expectations | Validate incoming data against expectations |
| Transformation | dbt Core | SQL-based transformations (raw → staging → marts) |
| Storage | PostgreSQL | Data warehouse |
| ML Training | XGBoost + scikit-learn | Price forecasting models |
| Experiment Tracking | MLflow | Track model experiments and versioning |
| Model Serving | FastAPI | REST API for predictions |
| Visualization | Streamlit | Interactive dashboard |
| Containerization | Docker + Docker Compose | Reproducible deployment |
| CI/CD | GitHub Actions | Automated testing and linting |

---

## Data Sources

| Source | Frequency | Coverage | Access |
|--------|-----------|----------|--------|
| WFP VAM Price Database | Weekly/Monthly | 40+ Nigerian markets, 20+ commodities | Public API |
| World Bank Real-Time Prices | Weekly | ML-estimated prices for Nigerian markets | Public download |
| NBS Selected Food Prices | Monthly | National & state-level, 40+ items | PDF extraction |
| CBN Exchange Rates | Daily | Official & bureau de change rates | Public CSV |
| Open-Meteo | Daily | Weather data (rainfall, temperature) | Free API |

---

## Project Structure

```
nigeria-food-price-pipeline/
├── .github/
│   └── workflows/
│       ├── ci.yml                  # Lint, test, type-check
│       └── docker-build.yml        # Build and push images
├── airflow/
│   ├── dags/
│   │   ├── ingest_wfp.py
│   │   ├── ingest_nbs.py
│   │   ├── ingest_worldbank.py
│   │   ├── ingest_cbn.py
│   │   ├── ingest_weather.py
│   │   ├── run_dbt.py
│   │   ├── run_great_expectations.py
│   │   └── train_model.py
│   └── plugins/
├── dbt/
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_wfp_prices.sql
│   │   │   ├── stg_nbs_prices.sql
│   │   │   ├── stg_cbn_rates.sql
│   │   │   └── stg_weather.sql
│   │   ├── intermediate/
│   │   │   └── int_prices_unified.sql
│   │   └── marts/
│   │       ├── fct_daily_prices.sql
│   │       ├── fct_weekly_prices.sql
│   │       ├── dim_markets.sql
│   │       └── dim_commodities.sql
│   ├── seeds/
│   │   ├── markets.csv
│   │   └── commodities.csv
│   ├── tests/
│   └── dbt_project.yml
├── great_expectations/
│   ├── expectations/
│   │   ├── wfp_prices_suite.json
│   │   ├── nbs_prices_suite.json
│   │   └── weather_data_suite.json
│   └── great_expectations.yml
├── ml/
│   ├── features/
│   │   └── feature_engineering.py
│   ├── training/
│   │   ├── train.py
│   │   └── evaluate.py
│   ├── serving/
│   │   ├── app.py                  # FastAPI application
│   │   └── schemas.py
│   └── experiments/
│       └── configs/
├── ingestion/
│   ├── sources/
│   │   ├── wfp_client.py
│   │   ├── nbs_extractor.py
│   │   ├── worldbank_client.py
│   │   ├── cbn_client.py
│   │   └── weather_client.py
│   └── utils/
│       ├── pdf_parser.py
│       └── validators.py
├── dashboard/
│   ├── app.py                      # Streamlit application
│   ├── pages/
│   │   ├── price_trends.py
│   │   ├── forecasts.py
│   │   └── data_quality.py
│   └── components/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── docker/
│   ├── Dockerfile.airflow
│   ├── Dockerfile.api
│   ├── Dockerfile.dashboard
│   └── Dockerfile.ml
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── Makefile
├── .env.example
└── docs/
    ├── architecture.md
    ├── data_dictionary.md
    ├── setup.md
    └── api_reference.md
```

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/<your-username>/nigeria-food-price-pipeline.git
cd nigeria-food-price-pipeline

# Copy environment variables
cp .env.example .env

# Start all services
docker-compose up -d

# Access services
# Airflow UI:    http://localhost:8080
# MLflow UI:     http://localhost:5000
# FastAPI Docs:  http://localhost:8000/docs
# Streamlit:     http://localhost:8501
```

---

## Key Features

- **Automated ingestion** from 5 data sources on configurable schedules
- **Data quality gates** — pipeline fails fast if data doesn't meet expectations
- **Dimensional model** — star schema optimized for analytical queries
- **ML forecasting** — 7-day and 30-day price predictions per commodity per market
- **REST API** — query predictions programmatically
- **Interactive dashboard** — explore trends, compare markets, view forecasts
- **Fully containerized** — one command to run the entire platform
- **CI/CD** — automated testing on every push

---

## Contributing

Contributions are welcome. Please read the [contributing guidelines](docs/CONTRIBUTING.md) before submitting a pull request.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [World Food Programme](https://www.wfp.org/) — VAM food price data
- [World Bank](https://www.worldbank.org/) — Real-Time Prices dataset
- [National Bureau of Statistics, Nigeria](https://www.nigerianstat.gov.ng/) — Selected Food Prices Watch
- [Central Bank of Nigeria](https://www.cbn.gov.ng/) — Exchange rate data
- [Open-Meteo](https://open-meteo.com/) — Weather data API

---

## Academic Context

This project is developed as part of the **MIT 8212 – Seminar: Industry Applications and Management in Information Technology** at Miva Open University. It demonstrates the application of data engineering and machine learning engineering to solve a real problem in the Nigerian economy.

**Title:** Design and Implementation of an End-to-End Data Pipeline for Real-Time Food Price Monitoring and Forecasting in Nigerian Markets

**Key Results:**
- 140,000+ rows ingested from 3 public data sources (fully automated)
- 22 data quality checks passing across 5 raw tables
- Star schema with 105,950 daily price observations across 74 markets
- XGBoost achieves 36% MAPE improvement over naive baseline for 30-day Oil Palm forecasts
- REST API serving predictions in <500ms
- Interactive 4-page Streamlit dashboard
- Full Docker Compose one-command deployment
