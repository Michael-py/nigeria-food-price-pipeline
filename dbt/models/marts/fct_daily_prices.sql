-- Fact table: Daily food prices by market and commodity
-- Aggregates across sources, includes category and unit for display

with unified_prices as (
    select * from {{ ref('int_prices_unified') }}
),

daily_agg as (
    select
        price_date,
        market_name,
        commodity_name,
        max(category) as category,
        max(unit_name) as unit_name,
        avg(price_ngn) as price_ngn,
        min(price_ngn) as price_min_ngn,
        max(price_ngn) as price_max_ngn,
        count(*) as source_count
    from unified_prices
    group by price_date, market_name, commodity_name
)

select
    {{ dbt_utils.generate_surrogate_key(['price_date', 'market_name', 'commodity_name']) }} as price_id,
    price_date,
    market_name,
    commodity_name,
    category,
    unit_name,
    round(price_ngn::numeric, 2) as price_ngn,
    round(price_min_ngn::numeric, 2) as price_min_ngn,
    round(price_max_ngn::numeric, 2) as price_max_ngn,
    source_count
from daily_agg
