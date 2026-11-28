-- SELECT * on purpose: a column added to accounting.shipping must reach this model (IN-3).
select *
from {{ source('accounting', 'shipping') }}
