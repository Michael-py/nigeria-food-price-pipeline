-- Intermediate: Unify prices from all sources with commodity name harmonization
-- Cleans names, removes zone aggregates, filters unit-mixed outliers

with wfp as (
    select price_date, market_name, commodity_name, unit_name, price_ngn, 'WFP' as source
    from {{ ref('stg_wfp_prices') }}
),

worldbank as (
    select price_date, market_name, commodity_name, unit_name, price_ngn, 'WorldBank' as source
    from {{ ref('stg_worldbank_prices') }}
),

nbs as (
    select price_date, market_name, commodity_name, unit_name, price_ngn, 'NBS' as source
    from {{ ref('stg_nbs_prices') }}
),

raw_unified as (
    select * from wfp
    union all
    select * from worldbank
    union all
    select * from nbs
),

mapping as (
    select * from {{ ref('commodity_mapping') }}
),

harmonized as (
    select
        u.price_date,
        u.market_name,
        coalesce(m.clean_name, u.commodity_name) as commodity_name,
        coalesce(m.unit, u.unit_name) as unit_name,
        coalesce(m.category, 'Other') as category,
        u.price_ngn,
        u.source
    from raw_unified u
    left join mapping m on u.commodity_name = m.raw_name
    where u.price_ngn > 0
      and length(coalesce(m.clean_name, u.commodity_name)) > 3
      and lower(coalesce(m.clean_name, u.commodity_name)) not in (
        'bottle', 'loose', 'one)', 'penny 2kg', 'sold loose',
        'medium size', 'medium size fresh', 'specify'
      )
      and u.market_name not in (
        'National', 'Market Average',
        'North Central', 'North East', 'North West',
        'South East', 'South South', 'South West'
      )
),

-- Compute IQR bounds per commodity to filter unit-mixed outliers
commodity_bounds as (
    select
        commodity_name,
        percentile_cont(0.25) within group (order by price_ngn) as q1,
        percentile_cont(0.75) within group (order by price_ngn) as q3
    from harmonized
    group by commodity_name
)

-- Remove extreme outliers (>5x IQR above Q3 or below Q1)
-- This catches bag prices mixed with per-KG prices
select
    h.price_date,
    h.market_name,
    h.commodity_name,
    h.unit_name,
    h.category,
    h.price_ngn,
    h.source
from harmonized h
join commodity_bounds b on h.commodity_name = b.commodity_name
where h.price_ngn between (b.q1 - 3 * (b.q3 - b.q1)) and (b.q3 + 3 * (b.q3 - b.q1))
