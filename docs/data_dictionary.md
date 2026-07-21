# Data Dictionary

## Raw Layer (schema: `raw`)

### raw.wfp_prices
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Auto-increment primary key |
| country_name | VARCHAR(100) | Country (always "Nigeria") |
| market_name | VARCHAR(200) | Market name (e.g., "Lagos (Mile 12)") |
| commodity_name | VARCHAR(200) | Commodity name (e.g., "Rice (imported)") |
| currency_name | VARCHAR(50) | Currency (always "NGN") |
| unit_name | VARCHAR(50) | Unit of measurement (KG, Litre, etc.) |
| price | DECIMAL(12,2) | Price in specified currency per unit |
| price_date | DATE | Date of price observation |
| source | VARCHAR(50) | Always "WFP" |
| ingested_at | TIMESTAMP | When the row was loaded |

### raw.nbs_prices
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Auto-increment primary key |
| commodity_name | VARCHAR(200) | Commodity name |
| unit | VARCHAR(50) | Unit of measurement |
| price | DECIMAL(12,2) | Average price in NGN |
| report_month | DATE | Month of the report (1st of month) |
| state | VARCHAR(100) | Nigerian state or "National Average" |
| source | VARCHAR(50) | Always "NBS" |
| ingested_at | TIMESTAMP | When the row was loaded |

### raw.worldbank_prices
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Auto-increment primary key |
| country_code | VARCHAR(10) | Always "NGA" |
| market_name | VARCHAR(200) | Market name |
| commodity_name | VARCHAR(200) | Commodity name |
| unit | VARCHAR(50) | Unit of measurement |
| price | DECIMAL(12,2) | ML-estimated price in local currency |
| price_date | DATE | Date of price estimate |
| source | VARCHAR(50) | Always "WorldBank" |
| ingested_at | TIMESTAMP | When the row was loaded |

### raw.cbn_rates
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Auto-increment primary key |
| rate_date | DATE | Date of exchange rate |
| currency | VARCHAR(10) | Foreign currency (e.g., "USD") |
| buying_rate | DECIMAL(12,4) | Buying rate (NGN per unit of foreign currency) |
| central_rate | DECIMAL(12,4) | Central/official rate |
| selling_rate | DECIMAL(12,4) | Selling rate |
| source | VARCHAR(50) | Always "CBN" |
| ingested_at | TIMESTAMP | When the row was loaded |

### raw.weather
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Auto-increment primary key |
| market_name | VARCHAR(200) | Market location name |
| latitude | DECIMAL(8,4) | Latitude of market |
| longitude | DECIMAL(8,4) | Longitude of market |
| weather_date | DATE | Date of weather observation |
| temperature_max | DECIMAL(5,1) | Maximum temperature (°C) |
| temperature_min | DECIMAL(5,1) | Minimum temperature (°C) |
| precipitation_mm | DECIMAL(6,1) | Total precipitation (mm) |
| humidity_pct | DECIMAL(5,1) | Average relative humidity (%) |
| source | VARCHAR(50) | Always "OpenMeteo" |
| ingested_at | TIMESTAMP | When the row was loaded |

---

## Mart Layer (schema: `marts`)

### marts.fct_daily_prices
| Column | Type | Description |
|--------|------|-------------|
| price_id | VARCHAR | Surrogate key (hash of date+market+commodity) |
| price_date | DATE | Date of observation |
| market_name | VARCHAR | Market name |
| commodity_name | VARCHAR | Commodity name |
| price_ngn | DECIMAL | Average price (NGN) across sources |
| price_min_ngn | DECIMAL | Minimum observed price |
| price_max_ngn | DECIMAL | Maximum observed price |
| source_count | INT | Number of sources reporting |
| sources | ARRAY | List of sources |

### marts.dim_markets
| Column | Type | Description |
|--------|------|-------------|
| market_id | INT | Primary key |
| market_name | VARCHAR | Market name |
| state | VARCHAR | Nigerian state |
| geopolitical_zone | VARCHAR | Zone (North-West, South-East, etc.) |
| latitude | DECIMAL | Latitude |
| longitude | DECIMAL | Longitude |

### marts.dim_commodities
| Column | Type | Description |
|--------|------|-------------|
| commodity_id | INT | Primary key |
| commodity_name | VARCHAR | Commodity name |
| category | VARCHAR | Category (Cereals, Legumes, Tubers, etc.) |
| standard_unit | VARCHAR | Standard unit (KG, Litre, Piece) |
| is_staple | BOOLEAN | Whether it's a staple food |

---

## ML Layer (schema: `ml`)

### ml.predictions
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Auto-increment primary key |
| market_name | VARCHAR | Market name |
| commodity_name | VARCHAR | Commodity name |
| prediction_date | DATE | Date the prediction is for |
| forecast_horizon_days | INT | How far ahead (7 or 30) |
| predicted_price | DECIMAL | Predicted price (NGN) |
| lower_bound | DECIMAL | Lower confidence interval |
| upper_bound | DECIMAL | Upper confidence interval |
| model_version | VARCHAR | MLflow model version |
| created_at | TIMESTAMP | When prediction was generated |
