-- Staging model for World Bank Real-Time Prices
-- Cleans, deduplicates, and standardizes

with source as (
    select * from {{ source('raw', 'worldbank_prices') }}
),

cleaned as (
    select
        market_name,
        commodity_name,
        unit as unit_name,
        price as price_ngn,
        price_date,
        source,
        ingested_at,
        row_number() over (
            partition by market_name, commodity_name, price_date
            order by ingested_at desc
        ) as row_num
    from source
    where price > 0
      and price_date is not null
      and market_name is not null
      and commodity_name is not null
)

select
    market_name,
    commodity_name,
    unit_name,
    price_ngn,
    price_date,
    source
from cleaned
where row_num = 1
