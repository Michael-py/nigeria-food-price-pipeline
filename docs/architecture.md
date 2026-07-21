# System Architecture

## Overview

The Nigeria Food Price Intelligence Pipeline follows a modern data lakehouse architecture with clear separation of concerns across layers.

## Design Principles

1. **Modularity** — Each component is independently deployable and testable
2. **Idempotency** — Pipeline runs are safe to retry without side effects
3. **Data Immutability** — Raw data is never modified; transformations create new tables
4. **Observability** — Data quality, pipeline health, and model performance are all monitored
5. **Reproducibility** — Docker Compose ensures identical environments everywhere

## Layer Architecture

### 1. Ingestion Layer
- Pulls data from 5 external sources
- Handles retries, rate limits, and partial failures
- Writes to `raw` schema (append-only)

### 2. Validation Layer (Great Expectations)
- Runs after each ingestion
- Checks: completeness, freshness, value ranges, schema conformity
- Blocks downstream processing on failure

### 3. Transformation Layer (dbt)
- **Staging:** Clean, cast, standardize each source independently
- **Intermediate:** Unify across sources, resolve conflicts
- **Marts:** Star schema for analytics (facts + dimensions)

### 4. ML Layer
- **Feature Engineering:** Time-series features, weather, FX rates
- **Training:** XGBoost with MLflow tracking
- **Serving:** FastAPI REST endpoint

### 5. Presentation Layer
- **API:** Programmatic access to predictions
- **Dashboard:** Visual exploration (Streamlit)

### 6. Orchestration Layer (Airflow)
- Schedules all pipeline stages
- Manages dependencies between stages
- Provides monitoring and alerting

## Data Flow

```
External Sources → Ingest → Raw DB → Validate → Transform → Marts DB
                                                                 │
                                                    ┌────────────┼────────────┐
                                                    ▼            ▼            ▼
                                              ML Training    Dashboard      API
                                                    │
                                                    ▼
                                              MLflow Registry
                                                    │
                                                    ▼
                                              Model Serving
```

## Technology Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestrator | Airflow | Industry standard, excellent UI, well-documented |
| Transformation | dbt | SQL-first, version-controlled, testable, generates docs |
| Data Quality | Great Expectations | Declarative expectations, integrates with Airflow |
| ML Framework | XGBoost | Best-in-class for tabular time-series, fast training |
| Experiment Tracking | MLflow | Open source, model registry, artifact management |
| API Framework | FastAPI | Async, auto-docs, Pydantic validation, fast |
| Dashboard | Streamlit | Python-native, rapid prototyping, interactive |
| Database | PostgreSQL | Robust, supports schemas, well-supported by all tools |
| Containers | Docker Compose | Simple multi-service orchestration for development |
