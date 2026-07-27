-- Dimension: Markets
-- All unique markets from all sources, enriched with seed data

with observed_markets as (
    select distinct market_name
    from {{ ref('int_prices_unified') }}
),

seed_markets as (
    select
        market_name,
        state,
        geopolitical_zone,
        latitude,
        longitude
    from {{ ref('markets') }}
),

final as (
    select
        om.market_name,
        sm.state,
        sm.geopolitical_zone,
        sm.latitude,
        sm.longitude,
        case when sm.market_name is not null then true else false end as has_coordinates
    from observed_markets om
    left join seed_markets sm on om.market_name = sm.market_name
)

select * from final
