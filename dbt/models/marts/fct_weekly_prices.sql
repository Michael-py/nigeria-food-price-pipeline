-- Fact table: Weekly aggregated food prices
-- Useful for forecasting at weekly granularity

with daily as (
    select * from {{ ref('fct_daily_prices') }}
),

weekly_agg as (
    select
        date_trunc('week', price_date)::date as week_start,
        market_name,
        commodity_name,
        avg(price_ngn) as avg_price_ngn,
        min(price_ngn) as min_price_ngn,
        max(price_ngn) as max_price_ngn,
        count(*) as observation_count
    from daily
    group by date_trunc('week', price_date), market_name, commodity_name
)

select
    {{ dbt_utils.generate_surrogate_key(['week_start', 'market_name', 'commodity_name']) }} as weekly_price_id,
    week_start,
    market_name,
    commodity_name,
    round(avg_price_ngn::numeric, 2) as avg_price_ngn,
    round(min_price_ngn::numeric, 2) as min_price_ngn,
    round(max_price_ngn::numeric, 2) as max_price_ngn,
    observation_count
from weekly_agg
