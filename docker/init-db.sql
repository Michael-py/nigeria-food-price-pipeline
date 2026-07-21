-- Initialize databases for all services
CREATE DATABASE airflow;
CREATE DATABASE mlflow;

-- Create schemas in the main food_prices database
\c food_prices;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS ml;

-- Raw tables
CREATE TABLE IF NOT EXISTS raw.wfp_prices (
    id SERIAL PRIMARY KEY,
    country_name VARCHAR(100),
    market_name VARCHAR(200),
    commodity_name VARCHAR(200),
    currency_name VARCHAR(50),
    unit_name VARCHAR(50),
    price DECIMAL(12, 2),
    price_date DATE,
    source VARCHAR(50) DEFAULT 'WFP',
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.nbs_prices (
    id SERIAL PRIMARY KEY,
    commodity_name VARCHAR(200),
    unit VARCHAR(50),
    price DECIMAL(12, 2),
    report_month DATE,
    state VARCHAR(100),
    source VARCHAR(50) DEFAULT 'NBS',
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.worldbank_prices (
    id SERIAL PRIMARY KEY,
    country_code VARCHAR(10),
    market_name VARCHAR(200),
    commodity_name VARCHAR(200),
    unit VARCHAR(50),
    price DECIMAL(12, 2),
    price_date DATE,
    source VARCHAR(50) DEFAULT 'WorldBank',
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.cbn_rates (
    id SERIAL PRIMARY KEY,
    rate_date DATE,
    currency VARCHAR(10),
    buying_rate DECIMAL(12, 4),
    central_rate DECIMAL(12, 4),
    selling_rate DECIMAL(12, 4),
    source VARCHAR(50) DEFAULT 'CBN',
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.weather (
    id SERIAL PRIMARY KEY,
    market_name VARCHAR(200),
    latitude DECIMAL(8, 4),
    longitude DECIMAL(8, 4),
    weather_date DATE,
    temperature_max DECIMAL(5, 1),
    temperature_min DECIMAL(5, 1),
    precipitation_mm DECIMAL(6, 1),
    humidity_pct DECIMAL(5, 1),
    source VARCHAR(50) DEFAULT 'OpenMeteo',
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data quality logging
CREATE TABLE IF NOT EXISTS raw.data_quality_log (
    id SERIAL PRIMARY KEY,
    suite_name VARCHAR(200),
    run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN,
    statistics JSONB,
    results_summary TEXT
);

-- ML features and predictions
CREATE TABLE IF NOT EXISTS ml.features (
    id SERIAL PRIMARY KEY,
    market_name VARCHAR(200),
    commodity_name VARCHAR(200),
    feature_date DATE,
    features JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ml.predictions (
    id SERIAL PRIMARY KEY,
    market_name VARCHAR(200),
    commodity_name VARCHAR(200),
    prediction_date DATE,
    forecast_horizon_days INTEGER,
    predicted_price DECIMAL(12, 2),
    lower_bound DECIMAL(12, 2),
    upper_bound DECIMAL(12, 2),
    model_version VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_wfp_prices_date ON raw.wfp_prices(price_date);
CREATE INDEX idx_wfp_prices_market ON raw.wfp_prices(market_name);
CREATE INDEX idx_wfp_prices_commodity ON raw.wfp_prices(commodity_name);
CREATE INDEX idx_nbs_prices_month ON raw.nbs_prices(report_month);
CREATE INDEX idx_cbn_rates_date ON raw.cbn_rates(rate_date);
CREATE INDEX idx_weather_date ON raw.weather(weather_date);
CREATE INDEX idx_predictions_date ON ml.predictions(prediction_date);
CREATE INDEX idx_predictions_commodity ON ml.predictions(commodity_name);
