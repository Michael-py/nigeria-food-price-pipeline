#!/bin/bash
set -e

# Initialize the database (runs migrations, safe to run multiple times)
airflow db migrate

# Create admin user if it doesn't already exist
airflow users create \
    --username "${AIRFLOW_ADMIN_USER:-admin}" \
    --password "${AIRFLOW_ADMIN_PASSWORD:-admin}" \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    2>/dev/null || true

# Run whatever command was passed (webserver or scheduler)
exec airflow "$@"
