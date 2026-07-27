-- Staging model for CBN exchange rates
-- Provides USD/NGN rate for import price adjustments

with source as (
    select * from {{ source('raw', 'cbn_rates') }}
),

cleaned as (
    select
        rate_date,
        currency,
        buying_rate,
        central_rate,
        selling_rate,
        source
    from source
    where central_rate > 0
      and rate_date is not null
)

select * from cleaned
