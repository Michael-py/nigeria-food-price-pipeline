-- Fact table: Monthly aggregated food prices
-- Best granularity for comparing across all sources (NBS is monthly)

with daily as (
    select * from {{ ref('fct_daily_prices') }}
),

monthly_agg as (
    select
        date_trunc('month', price_date)::date as month_start,
        market_name,
        commodity_name,
        avg(price_ngn) as avg_price_ngn,
        min(price_ngn) as min_price_ngn,
        max(price_ngn) as max_price_ngn,
        max(price_ngn) - min(price_ngn) as price_range_ngn,
        count(*) as observation_count
    from daily
    group by date_trunc('month', price_date), market_name, commodity_name
)

select
    {{ dbt_utils.generate_surrogate_key(['month_start', 'market_name', 'commodity_name']) }} as monthly_price_id,
    month_start,
    market_name,
    commodity_name,
    round(avg_price_ngn::numeric, 2) as avg_price_ngn,
    round(min_price_ngn::numeric, 2) as min_price_ngn,
    round(max_price_ngn::numeric, 2) as max_price_ngn,
    round(price_range_ngn::numeric, 2) as price_range_ngn,
    observation_count
from monthly_agg
