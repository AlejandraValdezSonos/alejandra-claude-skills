-- Hash over every pre-existing column: the changed view must equal production (example query)
select 'changed' as side, count(*) as n, hash_agg(sale_id, sale_date, units, revenue) as h
from analytics_dev.sales.sales_summary
union all
select 'production', count(*), hash_agg(sale_id, sale_date, units, revenue)
from analytics.sales.sales_summary;
