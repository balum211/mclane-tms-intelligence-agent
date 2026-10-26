-- Reference answers for common natural-language questions (DuckDB / PostgreSQL syntax;
-- in BigQuery qualify tables as `project.mclane_tms.<table>`). Dates assume as-of 2026-10-27.

-- "Which carriers had the worst on-time performance last quarter?"
SELECT carrier_id, carrier_name, loads, on_time_pct FROM v_carrier_scorecard ORDER BY on_time_pct LIMIT 5;

-- "What is our on-time % by customer for the last 30 days vs target?"
SELECT v.customer_name, cu.on_time_target_pct,
       1.0 * SUM(CASE WHEN v.on_time_flag THEN 1 ELSE 0 END) / COUNT(*) AS on_time_pct
FROM v_stop_service v JOIN customers cu ON cu.customer_id = v.customer_id
WHERE v.delivery_date BETWEEN '2026-09-28' AND '2026-10-27'
GROUP BY 1, 2 ORDER BY on_time_pct;

-- "Which lanes lost money last month?"
SELECT lane, COUNT(*) AS loads, SUM(margin) AS margin, 1.0 * SUM(margin) / SUM(total_revenue) AS margin_pct,
       1.0 * SUM(empty_miles) / SUM(total_miles) AS empty_mile_pct
FROM v_load_profitability WHERE load_date BETWEEN '2026-09-28' AND '2026-10-27'
GROUP BY lane HAVING SUM(margin) < 0 ORDER BY margin;

-- "How much detention did BurgerBarn generate and how much did we bill?"
SELECT SUM(s.detention_minutes) / 60.0 AS detention_hours, SUM(i.detention_billed) AS billed
FROM stops s JOIN locations l ON l.location_id = s.location_id JOIN customers c ON c.customer_id = l.customer_id
LEFT JOIN invoices i ON i.order_id = s.order_id
WHERE c.customer_name = 'BurgerBarn';

-- "Which carrier invoices billed a rate above contract?"
SELECT ci.carrier_invoice_id, ci.carrier_id, ci.billed_rate_per_mile, r.rate_per_mile AS contract_rate
FROM carrier_invoices ci JOIN loads l ON l.load_id = ci.load_id
JOIN carrier_rates r ON r.carrier_id = ci.carrier_id AND r.origin_dc_id = l.origin_dc_id
 AND r.dest_state = l.dest_region_state AND r.equipment_type = l.equipment_type
WHERE ci.billed_rate_per_mile > r.rate_per_mile * 1.01
ORDER BY ci.billed_rate_per_mile - r.rate_per_mile DESC LIMIT 20;
