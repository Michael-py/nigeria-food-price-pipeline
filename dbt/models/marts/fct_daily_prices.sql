-- Fact table: Daily food prices by market and commodity
-- One row per market per commodity per day (deduplicated, source-prioritized)

with unified_prices as (
    select * from {{ ref('int_prices_unified') }}
),

daily_agg as (
    select
        price_date,
        market_name,
        commodity_name,
        -- If multiple sources have data for same day, take the average
        avg(price_ngn) as price_ngn,
        min(price_ngn) as price_min_ngn,
        max(price_ngn) as price_max_ngn,
        count(*) as source_count,
        array_agg(distinct source) as sources
    from unified_prices
    group by price_date, market_name, commodity_name
)

select
    {{ dbt_utils.generate_surrogate_key(['price_date', 'market_name', 'commodity_name']) }} as price_id,
    price_date,
    market_name,
    commodity_name,
    round(price_ngn, 2) as price_ngn,
    round(price_min_ngn, 2) as price_min_ngn,
    round(price_max_ngn, 2) as price_max_ngn,
    source_count,
    sources
from daily_agg
