-- A rename, two transformations and a filter.
select
    order_id,
    product_id,
    quantity,
    item_cost_currency_code as currency_code,
    item_cost_units + item_cost_nanos / 1e9 as item_cost,
    (item_cost_units + item_cost_nanos / 1e9) * quantity as line_total
from {{ source('accounting', 'orderitem') }}
where quantity > 0
