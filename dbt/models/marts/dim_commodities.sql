-- Dimension: Commodities
-- All unique commodities from all sources, enriched with seed data

with observed_commodities as (
    select distinct commodity_name
    from {{ ref('int_prices_unified') }}
),

seed_commodities as (
    select
        commodity_name,
        category,
        standard_unit,
        is_staple
    from {{ ref('commodities') }}
),

final as (
    select
        oc.commodity_name,
        sc.category,
        sc.standard_unit,
        coalesce(sc.is_staple, false) as is_staple,
        case when sc.commodity_name is not null then true else false end as in_seed_list
    from observed_commodities oc
    left join seed_commodities sc on lower(oc.commodity_name) = lower(sc.commodity_name)
)

select * from final
