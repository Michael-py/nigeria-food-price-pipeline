FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[ml]" mlflow

EXPOSE 5000

CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000"]
