-- Intermediate model: Unify prices from all sources
-- Standardizes units to NGN/kg where possible

with wfp as (
    select
        price_date,
        market_name,
        commodity_name,
        price_ngn,
        'WFP' as source
    from {{ ref('stg_wfp_prices') }}
),

nbs as (
    select
        report_month as price_date,
        state as market_name,
        commodity_name,
        cast(price as decimal(12, 2)) as price_ngn,
        'NBS' as source
    from {{ ref('stg_nbs_prices') }}
),

worldbank as (
    select
        price_date,
        market_name,
        commodity_name,
        cast(price as decimal(12, 2)) as price_ngn,
        'WorldBank' as source
    from {{ ref('stg_worldbank_prices') }}
),

unified as (
    select * from wfp
    union all
    select * from nbs
    union all
    select * from worldbank
)

select * from unified
where price_ngn > 0
