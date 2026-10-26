-- Production-scale delay prediction with BigQuery ML (logistic regression).
-- Mirrors the in-agent explainable model (tms_agent/tools/predict.py) with the same pre-dispatch features.
-- Replace YOUR_PROJECT (deployment/setup_gcp.sh does this automatically).

-- 1. Feature view: one row per load, label = any stop missed its window.
CREATE OR REPLACE VIEW `YOUR_PROJECT.mclane_tms.v_load_delay_features` AS
WITH receiver AS (
  SELECT location_id,
         SAFE_DIVIDE(COUNTIF(NOT on_time_flag) + 5 * 0.1, COUNT(*) + 5) AS receiver_late_rate
  FROM `YOUR_PROJECT.mclane_tms.stops`
  WHERE arrival_ts IS NOT NULL
  GROUP BY location_id
)
SELECT
  l.load_id, l.load_date, l.load_status,
  CONCAT(l.origin_dc_id, '-', FORMAT_DATE('%a', l.load_date)) AS dc_day,
  l.carrier_id,
  CONCAT(l.equipment_type, IF(IFNULL(t.reefer_unit_age_years, 0) >= 9, '-OLD_REEFER', '')) AS equipment,
  l.stop_count,
  l.total_miles,
  MAX(r.receiver_late_rate) AS worst_receiver_late_rate,
  IF(l.load_status = 'COMPLETED', CAST(COUNTIF(s.on_time_flag = FALSE) > 0 AS INT64), NULL) AS late_label
FROM `YOUR_PROJECT.mclane_tms.loads` l
JOIN `YOUR_PROJECT.mclane_tms.stops` s USING (load_id)
LEFT JOIN receiver r ON r.location_id = s.location_id
LEFT JOIN `YOUR_PROJECT.mclane_tms.trailers` t ON t.trailer_id = l.trailer_id
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8;

-- 2. Train on completed loads, holding out the last 14 days.
CREATE OR REPLACE MODEL `YOUR_PROJECT.mclane_tms.load_delay_model`
OPTIONS (
  model_type = 'LOGISTIC_REG',
  input_label_cols = ['late_label'],
  auto_class_weights = TRUE,
  enable_global_explain = TRUE,
  data_split_method = 'NO_SPLIT'
) AS
SELECT dc_day, carrier_id, equipment, stop_count, total_miles, worst_receiver_late_rate, late_label
FROM `YOUR_PROJECT.mclane_tms.v_load_delay_features`
WHERE load_status = 'COMPLETED'
  AND load_date < DATE_SUB((SELECT MAX(load_date) FROM `YOUR_PROJECT.mclane_tms.loads` WHERE load_status = 'COMPLETED'), INTERVAL 14 DAY);

-- 3. Evaluate on the holdout (precision, recall, roc_auc, ...).
SELECT * FROM ML.EVALUATE(
  MODEL `YOUR_PROJECT.mclane_tms.load_delay_model`,
  (SELECT * FROM `YOUR_PROJECT.mclane_tms.v_load_delay_features`
   WHERE load_status = 'COMPLETED'
     AND load_date >= DATE_SUB((SELECT MAX(load_date) FROM `YOUR_PROJECT.mclane_tms.loads` WHERE load_status = 'COMPLETED'), INTERVAL 14 DAY)));

-- 4. Score tomorrow's planned loads with per-load feature attributions.
SELECT load_id, predicted_late_label_probs, top_feature_attributions
FROM ML.EXPLAIN_PREDICT(
  MODEL `YOUR_PROJECT.mclane_tms.load_delay_model`,
  (SELECT * FROM `YOUR_PROJECT.mclane_tms.v_load_delay_features` WHERE load_status IN ('PLANNED', 'DISPATCHED')),
  STRUCT(3 AS top_k_features));
