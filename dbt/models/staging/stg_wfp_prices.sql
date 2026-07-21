-- Staging model for WFP food price data
-- Cleans, casts types, and standardizes column names

with source as (
    select * from {{ source('raw', 'wfp_prices') }}
),

cleaned as (
    select
        market_name,
        commodity_name,
        currency_name,
        unit_name,
        cast(price as decimal(12, 2)) as price_ngn,
        cast(price_date as date) as price_date,
        source,
        ingested_at
    from source
    where price > 0
      and price_date is not null
      and market_name is not null
      and commodity_name is not null
)

select * from cleaned
