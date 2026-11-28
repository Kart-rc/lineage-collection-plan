-- Join-heavy on purpose (BL-5): three inputs joined on order_id and grouped by it.
-- The join and group-by keys are indirect dependencies of the whole table, stored once, not once per column.
with items as (
    select
        order_id,
        sum(quantity) as item_count,
        sum(line_total) as items_value,
        min(currency_code) as currency_code
    from {{ ref('stg_order_items') }}
    group by order_id
)
select
    o.order_id,
    i.item_count,
    i.items_value,
    s.shipping_cost_units + s.shipping_cost_nanos / 1e9 as shipping_cost,
    i.items_value + s.shipping_cost_units + s.shipping_cost_nanos / 1e9 as order_value,
    i.currency_code,
    s.country
from {{ ref('stg_orders') }} as o
join items as i on i.order_id = o.order_id
join {{ ref('stg_shipping') }} as s on s.order_id = o.order_id
