-- Staging model for NBS Selected Food Prices Watch
-- Standardizes zonal/national price data

with source as (
    select * from {{ source('raw', 'nbs_prices') }}
),

cleaned as (
    select
        commodity_name,
        unit as unit_name,
        price as price_ngn,
        report_month as price_date,
        state as market_name,
        source,
        ingested_at,
        row_number() over (
            partition by commodity_name, state, report_month
            order by ingested_at desc
        ) as row_num
    from source
    where price > 0
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
