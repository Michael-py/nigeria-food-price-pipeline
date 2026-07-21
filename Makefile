.PHONY: setup lint test up down logs clean

# --- Development ---
setup:
	pip install -e ".[dev,ml,api,dashboard,quality]"
	pre-commit install

lint:
	ruff check .
	ruff format --check .
	mypy ingestion/ ml/

format:
	ruff format .
	ruff check --fix .

test:
	pytest tests/ -v --cov

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

# --- Docker ---
up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

build:
	docker-compose build

restart:
	docker-compose down && docker-compose up -d

# --- dbt ---
dbt-run:
	cd dbt && dbt run

dbt-test:
	cd dbt && dbt test

dbt-docs:
	cd dbt && dbt docs generate && dbt docs serve

# --- Data ---
ingest:
	python -m ingestion.sources.wfp_client
	python -m ingestion.sources.worldbank_client
	python -m ingestion.sources.cbn_client
	python -m ingestion.sources.weather_client

# --- ML ---
train:
	python -m ml.training.train

evaluate:
	python -m ml.training.evaluate

serve:
	uvicorn ml.serving.app:app --host 0.0.0.0 --port 8000 --reload

# --- Dashboard ---
dashboard:
	streamlit run dashboard/app.py

# --- Cleanup ---
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov
