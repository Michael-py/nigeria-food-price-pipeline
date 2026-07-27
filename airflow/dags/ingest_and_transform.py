"""
Food Price Pipeline DAG — Monthly Orchestration

Schedule: 1st of every month at 6:00 AM WAT
Pipeline: Ingest (all sources) → Validate → Transform (dbt) → Features → Train ML

This DAG refreshes all data sources monthly, validates quality,
rebuilds the analytical layer, and retrains forecasting models.
"""

from datetime import datetime, timedelta

from airflow.operators.bash import BashOperator

from airflow import DAG

# Project directory inside the Airflow container
PROJECT_DIR = "/opt/airflow"

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=1),
}

with DAG(
    dag_id="food_price_monthly_pipeline",
    default_args=default_args,
    description="Monthly ingestion, validation, transformation, and ML training for Nigerian food prices",
    schedule_interval="0 6 1 * *",  # 1st of every month at 6 AM
    start_date=datetime(2026, 7, 1),
    catchup=False,
    max_active_runs=1,
    tags=["food-prices", "pipeline", "monthly"],
    doc_md="""
    ## Nigeria Food Price Intelligence Pipeline

    **Runs monthly** to refresh data from all sources and retrain models.

    ### Pipeline Steps:
    1. **Ingest** — Pull latest data from WFP, World Bank, NBS, CBN, Weather
    2. **Validate** — Run Great Expectations + SQL quality checks
    3. **Transform** — dbt run (staging → intermediate → marts)
    4. **Test** — dbt test (data integrity checks)
    5. **Features** — Generate ML feature table
    6. **Train** — Retrain XGBoost models and register in MLflow
    """,
) as dag:
    # =========================================
    # STEP 1: DATA INGESTION (parallel)
    # =========================================

    ingest_wfp = BashOperator(
        task_id="ingest_wfp",
        bash_command=f"cd {PROJECT_DIR} && python -m ingestion.sources.wfp_client",
        doc="Ingest WFP food prices from HDX (87K+ rows, 68 markets)",
    )

    ingest_worldbank = BashOperator(
        task_id="ingest_worldbank",
        bash_command=f"cd {PROJECT_DIR} && python -m ingestion.sources.worldbank_client",
        doc="Ingest World Bank Real-Time Prices from HDX (26K+ rows, 74 markets)",
    )

    ingest_nbs = BashOperator(
        task_id="ingest_nbs",
        bash_command=f"cd {PROJECT_DIR} && python -m ingestion.sources.nbs_extractor",
        doc="Extract NBS Selected Food Prices from PDF reports (all 6 zones)",
    )

    ingest_cbn = BashOperator(
        task_id="ingest_cbn",
        bash_command=f"cd {PROJECT_DIR} && python -m ingestion.sources.cbn_client",
        retries=5,  # FX APIs can be flaky
        retry_delay=timedelta(minutes=5),
        doc="Fetch CBN USD/NGN exchange rates",
    )

    ingest_weather = BashOperator(
        task_id="ingest_weather",
        bash_command=f"cd {PROJECT_DIR} && python -m ingestion.sources.weather_client",
        retries=5,
        retry_delay=timedelta(minutes=5),
        doc="Fetch Open-Meteo weather data for 10 market locations",
    )

    # =========================================
    # STEP 2: DATA QUALITY VALIDATION
    # =========================================

    validate_data = BashOperator(
        task_id="validate_data_quality",
        bash_command=f"cd {PROJECT_DIR} && python -m ingestion.validate",
        doc="Run 22 quality checks (SQL + Great Expectations). Pipeline halts on failure.",
    )

    # =========================================
    # STEP 3: DBT TRANSFORMATION
    # =========================================

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"cd {PROJECT_DIR}/dbt && python -m dbt.cli.main seed",
        doc="Load reference data (commodity mappings, market-state mappings)",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {PROJECT_DIR}/dbt && python -m dbt.cli.main run",
        doc="Build staging → intermediate → mart models (star schema)",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {PROJECT_DIR}/dbt && python -m dbt.cli.main test",
        doc="Run 14 dbt data tests (uniqueness, not-null, referential integrity)",
    )

    # =========================================
    # STEP 4: ML FEATURE ENGINEERING
    # =========================================

    feature_engineering = BashOperator(
        task_id="feature_engineering",
        bash_command=f"cd {PROJECT_DIR} && python -m ml.features.feature_engineering",
        execution_timeout=timedelta(minutes=15),
        doc="Generate 37 time-series features for 325 market-commodity pairs",
    )

    # =========================================
    # STEP 5: ML MODEL TRAINING
    # =========================================

    train_models = BashOperator(
        task_id="train_models",
        bash_command=f"cd {PROJECT_DIR} && python -m ml.training.train_v2",
        execution_timeout=timedelta(minutes=30),
        doc="Train XGBoost models (7d + 30d horizons) and register in MLflow",
    )

    # =========================================
    # DEPENDENCIES
    # =========================================

    # All ingestion tasks run in parallel
    [ingest_wfp, ingest_worldbank, ingest_nbs, ingest_cbn, ingest_weather] >> validate_data

    # Validation gates transformation
    validate_data >> dbt_seed >> dbt_run >> dbt_test

    # ML runs after dbt completes
    dbt_test >> feature_engineering >> train_models
