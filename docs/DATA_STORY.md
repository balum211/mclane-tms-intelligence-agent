# Synthetic TMW data and the stories planted in it

`python -m tms_data.generate` builds a reproducible dataset (seed 42, as-of **2026-10-27**,
120 days). Every customer, carrier, driver and document is fictional.

| Entity | Rows | Notes |
|---|---|---|
| DCs / stores + restaurants | 8 / 1,303 | Temple TX, Dothan AL, Concord NC, Danville IL, Salt Lake City UT, Stockton CA, Ocala FL, Kansas City MO |
| Customers | 18 | Convenience, grocery, QSR, casual dining, military. Tiers set on-time targets (92-97%) and late penalties |
| Carriers | 10 | MCLN private fleet, 6 contract carriers, 3 brokers |
| Loads / stops / orders | 5.5k / 30k / 30k | Multi-stop DC routes. About 48 loads planned for tomorrow and about 40 in transit today |
| Carrier freight bills | 1.6k | EDI 210, PDF scans and emails, with planted overbilling and missing fields |
| Carrier rate contracts | ~200 | Carrier x lane x equipment, DOE fuel surcharge, detention and lumper rules |
| Telematics pings / exceptions | 2k / 5k | Reefer temperature, ETA, late, detention, shortage, HOS risk, breakdowns |

## Trimble TMW mapping

| This repo | TMW table | Key |
|---|---|---|
| orders | orderheader + freightdetail | ord_hdrnumber → order_id |
| loads | legheader | lgh_number → load_id |
| stops | stops | stp_number → stop_id |
| carriers | carrier | car_id → carrier_id |
| drivers / tractors / trailers | manpowerprofile / tractorprofile / trailerprofile | mpp_id / trc_number / trl_id |
| customers / locations | company (bill-to / shipper / consignee rows) | cmp_id |
| load_costs | paydetail (+ carrier settlements) | |
| invoices | invoiceheader + invoicedetail | |
| carrier_invoices | carrier freight bills / EDI 210 | |
| check_calls | checkcall | |

## Planted stories (what a good agent should find)

| # | Story | Signal in the data (default dataset) | Tool that finds it |
|---|---|---|---|
| 1 | **Redline Freight Brokers (CR006) is the worst carrier** | 73.6% on-time vs 88.3% private fleet. 60% tender acceptance. CONDITIONAL safety rating. About 30% of its invoices overbilled | `get_carrier_scorecard`, `audit_carrier_invoices` |
| 2 | **BurgerBarn detention is mostly unbilled** | Tight 6-10am docks at the DC04 restaurants, about $58k recoverable with only 26% of detention billed | `get_accessorial_leakage`, `get_detention_hotspots` |
| 3 | **Lane DC05→NV loses money** | −20% margin and 48% empty miles (no backhaul out of rural Nevada) | `get_lane_profitability`, `get_load_margin_outliers` |
| 4 | **Old reefer units cause temperature excursions** | 17.6% of loads on 9+ year units vs about 0.6% on newer units | `get_reefer_excursions` |
| 5 | **DC03 Concord is late on Mondays** | 52.6% Monday on-time, root cause LATE_DISPATCH | `get_late_delivery_summary(group_by="dc_day_of_week")` |
| 6 | **Diesel spike, surcharge lags** | +$0.68/gal in PADD3/PADD5 over the last 4 weeks. The surcharge uses a 2-week lag, so DC06 recovery fell from ~88% to ~81% | `get_fuel_surcharge_recovery(dc_id="DC06")` |
| 7 | **Drivers near their HOS limit on live loads** | About 12 drivers with < 2h drive time, several still with stops left | `get_at_risk_loads`, `get_driver_hos_status` |
| 8 | **Tobacco / candy shortages at DC02** | Tobacco / candy stops short 25% of the time at DC02 vs about 2% elsewhere (picking errors) | `get_open_exceptions`, NL-to-SQL |
| + | **Carrier overbilling** | 210 planted errors: rate above contract, inflated miles, fuel above the DOE table, detention with no evidence, duplicate detention, lumper with no receipt. Ground truth is in `data/generated/_truth_invoice_errors.csv` | `audit_carrier_invoices` |
| + | **Spot-market premium** | About 10% of outside loads move with a broker that has no lane contract, at a ~35% premium | `get_spot_vs_contract_premium` |
| + | **Chronically congested receivers** | Location-specific congestion, which is the learnable signal behind the delay model | `predict_load_delays` |

Regenerate with different parameters:

```bash
python -m tms_data.generate --days 180 --loads-per-dc-day 10 --seed 7 --as-of 2026-10-27
```
