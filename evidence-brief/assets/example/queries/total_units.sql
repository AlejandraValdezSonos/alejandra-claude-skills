-- Total units for the quarter, on the production table (example query)
select sum(units) as total_units
from analytics.sales.sales_summary
where fiscal_quarter_id = 202601;
