#!/bin/bash
set -e

echo "=== Airflow Entrypoint ==="

# Initialize/migrate the Airflow database
echo "Running db migrate..."
airflow db migrate

# Create admin user if it doesn't already exist
echo "Creating admin user..."
airflow users create \
    --username "${AIRFLOW_ADMIN_USER:-admin}" \
    --password "${AIRFLOW_ADMIN_PASSWORD:-admin}" \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    2>/dev/null || echo "Admin user already exists."

# Set the default connection for PostgreSQL (used by DAGs)
airflow connections add 'food_prices_db' \
    --conn-type 'postgres' \
    --conn-host 'postgres' \
    --conn-port '5432' \
    --conn-login "${POSTGRES_USER:-pipeline}" \
    --conn-password "${POSTGRES_PASSWORD:-changeme}" \
    --conn-schema "${POSTGRES_DB:-food_prices}" \
    2>/dev/null || echo "Connection already exists."

echo "=== Starting Airflow: $@ ==="

# Run whatever command was passed (webserver or scheduler)
exec airflow "$@"
