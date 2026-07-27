-- Staging model for weather data
-- Daily weather observations per market location

with source as (
    select * from {{ source('raw', 'weather') }}
),

cleaned as (
    select
        market_name,
        weather_date,
        temperature_max,
        temperature_min,
        precipitation_mm,
        humidity_pct,
        source
    from source
    where weather_date is not null
      and market_name is not null
)

select * from cleaned
