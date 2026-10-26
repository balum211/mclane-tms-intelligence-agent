# Verified examples (default dataset, DuckDB)

More reference queries: `sql/sample_questions.sql`.

**"How many stops did we deliver to TacoTrail restaurants in the last 7 days and what was the average dwell?"**

```sql
SELECT COUNT(*) AS stops, ROUND(AVG(dwell_minutes), 1) AS avg_dwell_min
FROM v_stop_service
WHERE customer_name = 'TacoTrail' AND delivery_date BETWEEN '2026-10-20' AND '2026-10-26';
```
→ 78 stops, 61.8 min. State the window you chose, because "last week" is ambiguous.

**"Which DC is worst on Mondays?"**

```sql
SELECT origin_dc_id,
       1.0 * SUM(CASE WHEN on_time_flag THEN 1 ELSE 0 END) / COUNT(*) AS on_time_pct
FROM v_stop_service
WHERE EXTRACT(DOW FROM delivery_date) = 1      -- BigQuery: EXTRACT(DAYOFWEEK FROM ...) = 2
GROUP BY 1 ORDER BY 2 LIMIT 3;
```
→ DC03 at 57.8% across all 120 days (52.6% in the curated tool's 90-day window).

**"Which carriers have the worst on-time performance?"**

```sql
SELECT carrier_id, carrier_name, loads, on_time_pct FROM v_carrier_scorecard ORDER BY on_time_pct LIMIT 3;
```
→ CR006 Redline Freight Brokers 72.9% (413 loads), then CR004 at 80.3%.

**Rejected:** `DELETE FROM loads` → "Rejected by SQL guard: Only SELECT / WITH queries are allowed."
