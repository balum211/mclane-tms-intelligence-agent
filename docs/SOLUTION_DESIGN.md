# TMS Intelligence: solution design

The structure follows the hackathon brief's output format. All numbers come from the bundled
synthetic dataset (as-of 2026-10-27, 120 days, 8 DCs). They show how the system behaves. They are
not a forecast of real McLane results.

## 0. Assumptions and open questions

**Assumptions**
- Trimble TMW (TMWSuite) is the system of record. Its core tables (orderheader, legheader, stops,
  freightdetail, carrier, manpowerprofile, tractorprofile, trailerprofile, paydetail, invoiceheader,
  checkcall) land in BigQuery or AlloyDB nightly or through CDC. The synthetic schema keeps that shape
  under readable names (see the mapping in [DATA_STORY.md](DATA_STORY.md)).
- Carrier freight bills arrive as EDI 210 (structured) or as scanned PDFs / emails stored in GCS.
- Contract rates are per carrier x lane (origin DC → destination state) x equipment, with a DOE-indexed
  fuel surcharge (base $1.25/gal, 6.0 mpg), $65/hr detention after 120 min free time, and lumper
  payable only with a receipt.
- Tendering in TMW happens through EDI 204 or the TMW API. In this MVP the write is **simulated** and
  logged. Nothing is sent to a carrier.
- Guardrail defaults (configurable): no auto-tender above **$2,500** or below **80% confidence**, and
  never to a carrier with a CONDITIONAL safety rating.

**Open questions for the business**
1. Which approval roles own tender overrides and invoice short-pays, and what dollar limits apply to each?
2. Is the delay SLA "any stop outside the appointment window" or a customer-specific tolerance?
3. Is there a lumper receipt or POD image store we can join to (it would close the LUMPER_NO_RECEIPT loop)?
4. Do we get TMW check calls in real time (Pub/Sub) or only in batch? That decides how fresh the at-risk view is.

## 1. Use-case prioritization (value vs effort)

| # | Capability | Business value | Effort | Hackathon MVP | Why |
|---|---|---|---|---|---|
| 3 | Freight invoice audit | **High**: direct, provable savings with $ per finding | Low/Med: deterministic rules + Gemini PDF extraction | ✅ Built | Fastest hard-dollar ROI. Every finding cites its evidence |
| 4 | NL questions with SQL | **High**: removes the analyst bottleneck for all personas | Low: schema-grounded NL-to-SQL + guard | ✅ Built | Front door for everyone and a strong live demo |
| 1 | Carrier recommendation + guardrailed auto-tender | **High**: on-time and cost every day | Med: scoring + approval flow + audit log | ✅ Built (TMW write simulated) | Shows safe autonomy (cap, confidence, human approval) |
| 2 | 24h delay prediction + mitigation | Med/High: protects service and penalties | Med: model + explanations | ✅ Built (explainable model + BQML path) | Proactive instead of reactive exception handling |
| 5 | Weekly insights | Medium: leadership visibility | Low: composes the above | ✅ Built | Turns all the signals into one ranked savings list |
| — | Looker dashboards | Medium | Low | Next | Point Looker / Looker Studio at the same views |
| — | Real-time re-planning on Pub/Sub events | High | High | 90-day pilot | Needs streaming check calls (and overlaps with the route optimization use case) |

## 2. Data model and pipeline

**Pipeline**

```
Trimble TMW (SQL Server) ──Datastream / nightly export──▶ BigQuery dataset mclane_tms  (or AlloyDB schema tms)
EDI 210 + scanned invoices ──GCS──▶ carrier_invoices (+ document_uri) ──Gemini extraction on demand
DOE weekly diesel index ──scheduled load──▶ fuel_prices
ADK agent (Agent Engine) ──read-only SA──▶ curated tools + guarded NL-to-SQL
                         ──write-only──▶ agent_decision_log  (+ Cloud Logging)
```

**Tables (18) and views (3)**, defined once in `tms_agent/schema.py` and rendered to BigQuery
(partitioned and clustered, with column descriptions), AlloyDB (keys, indexes, comments) and DuckDB.

| Domain | Tables (TMW equivalent) |
|---|---|
| Master data | customers (company bill-to), locations (company: DCs, stores, restaurants), carriers (carrier), drivers (manpowerprofile), tractors (tractorprofile), trailers (trailerprofile) |
| Execution | orders (orderheader + freightdetail), loads (legheader), stops (stops), check_calls (checkcall), exceptions |
| Money | load_costs (paydetail), invoices (invoiceheader), carrier_rates (rate tables), carrier_invoices (freight bills / EDI 210), fuel_prices (DOE) |
| Procurement | carrier_tenders (tender history) |
| Governance | agent_decision_log (new) |
| Views | v_load_profitability, v_stop_service, v_carrier_scorecard |

The NL-to-SQL agent is grounded on the same column descriptions, so the schema documentation and
the agent's knowledge never drift apart.

## 3. Agents per capability, with evaluation metrics

The coordinator (`tms_intelligence`) routes to seven specialists through ADK `AgentTool`, so it can
combine several answers into one. 36 tools in total.

| Capability | Agent / tools | How it decides | Evaluation metric | Result on synthetic data |
|---|---|---|---|---|
| Invoice audit | freight_audit_analyst: `audit_carrier_invoices`, `get_invoice_audit_detail`, `recommend_invoice_dispute`, `extract_and_audit_invoice_document` | Recomputes the expected linehaul (contract), fuel (DOE week x PADD), detention (stop minutes) and lumper (receipt). Spot loads are checked against the company-standard schedule | Catch rate (recall), precision, correct reason code | **Precision 100%, recall 100%, correct code 96%** on 210 planted errors. This is expected because the rules mirror the generator, so real-world rates will be lower and should be measured on audited history |
| Messy inputs | same | Missing fuel / illegible rate / no contract → `NEEDS_REVIEW` with the reason. Never estimated | % of invoices with gaps flagged rather than paid | Every missing-field invoice flagged (unit tested) |
| Delay prediction | service_exceptions_analyst: `predict_load_delays`, `get_delay_model_card` | Smoothed target encoding of pre-dispatch features (DC x weekday, carrier, equipment / reefer age, stops, riskiest receiver with leave-one-out, miles) combined in log-odds. Top drivers become mitigations | Time-based holdout (last 14 days): AUC, precision / recall at a threshold, top-decile lift | **AUC 0.72, top-decile lift 1.8x** (55% late vs 30% base); precision 0.51 / recall 0.30 at p ≥ 0.30 |
| Carrier recommendation | carrier_performance_analyst: `recommend_carrier_for_load`, `recommend_carriers`, `get_carrier_scorecard`, `get_tender_acceptance` | Score = 50% on-time (lane history when ≥ 3 loads) + 25% expected cost (contract + DOE fuel / spot premium / private fleet cost) + 25% acceptance − safety penalty. Private fleet only when drivers are free | Backtest: on-time and cost of the recommended carrier vs the carrier actually used; share of auto-tenders later overridden | Example: LGH0005494 moves from Redline to the private fleet, saving $351 and +23.5 pts on-time |
| Auto-tender guardrails | coordinator: `tender_load` | Recomputes cost and confidence from data, never from the chat. Within the cap and confidence → AUTO_EXECUTED. Otherwise ADK `request_confirmation` → APPROVED / REJECTED. Every path is logged | 0 auto-actions above the cap or below 80% (unit + runner tests) | Enforced in tests, including the real ADK runner emitting `adk_request_confirmation` |
| NL-to-SQL | tms_data_analyst: `get_tms_schema`, `run_tms_sql` | Schema-grounded, single SELECT, guard blocks DML / DDL / file functions, row cap, read-only connection | Execution accuracy on the ADK eval set; guard bypass attempts | 14-case eval set + 12 guard tests |
| Retail vs Restaurant OTD | delivery_performance_analyst: `get_otd_scorecard` | McLane rule per channel: Retail on time = not after the window end; Restaurant also not more than 15 min early. Grouped by channel, DC, customer, carrier or week, with penalty exposure | OTD % vs customer target, early vs late misses | Retail 84.6% vs Restaurant 78.9% (28 days); DC07 restaurants 71.0% |
| Dwell time change | delivery_performance_analyst: `get_dwell_time_changes` | Recent window vs baseline per customer / location / DC / channel; small samples set aside as LOW_SAMPLE; truck-hour cost from `TMS_TRUCK_HOUR_COST_USD` | Planted changes found, direction correct | Fresh Basket +27.7 min (~$151k a year), Cluck & Co −16.1 min |
| Geofence and geocodes | delivery_performance_analyst: `get_geofence_compliance`, `track_load` | Arrival source mix; locations where most arrivals are manual; corrected point = median of stopped ELD pings at arrival, otherwise NEEDS_REVIEW | Bad geocodes found, offset of the suggested fix | 92.1% auto-arrival; flagged locations are all ZIP_CENTROID, > 1 km off |
| PC*MILER miles | freight_audit_analyst: `check_pcmiler_miles`; fleet_operations_analyst: `get_out_of_route_miles` | TMS miles are PC*MILER practical; billed vs practical > 2% = MILES_INFLATED; odometer vs practical = out-of-route. Live PC*MILER Web Services when `PCMILER_API_KEY` is set, otherwise a labelled estimate | Out-of-route outliers found | Four DC08 drivers at ~13% vs ~2.5% fleet |
| Weekly insights | coordinator: `get_weekly_insights_pack` | Collects KPIs, lanes, carrier flags, audit, leakage, spot premium, tomorrow's risk, OTD by channel, dwell changes, out-of-route and geocode fixes | Rubric-based LLM judge (grounded, recommendation contract, actionable) | `evals/test_config.json` |

**Recommendation contract.** The global instruction requires every recommendation to show
*Reasoning, Data used, Confidence, $ impact*. The tools return those fields (`reasoning`,
`confidence`, `impact`, `window`) so the model never has to invent them.

**Audit trail.** Every tender (auto, pending, approved, rejected, blocked) and every dispute
recommendation is written to `agent_decision_log` with its rationale, the evidence JSON, confidence,
amount and actor.

## 4. Demo (5 minutes)

The full script is in [DEMO_SCRIPT.md](DEMO_SCRIPT.md). The three required moments:

**A. NL question → SQL → answer**
> "How many stops did we deliver to TacoTrail restaurants last week and what was the average dwell time?"

`tms_data_analyst` calls `get_tms_schema`, writes a single SELECT over `v_stop_service`, and
`run_tms_sql` executes it read-only. The answer is a small table followed by the SQL in a code block.

**B. Invoice audit**
> "How much are carriers overbilling us?" then "Audit invoice CINV0000069" and the scanned PDF `03_…CINV0000072.pdf`

- Last 90 days: **1,189 invoices, $1.48M billed, 152 overbilled, $15.8k overbilled (1.06% of spend),
  about $64k annualized**. Redline Freight Brokers accounts for $8.5k across 90 of its 305 invoices.
- CINV0000069: RATE_ABOVE_CONTRACT, billed $2.520/mi vs contract $2.170/mi (RATE00009), $142.02 over.
- Scanned CINV0000072: DETENTION_NO_EVIDENCE ($162.50 billed, 0 min of detention on the stop records) and
  a fuel surcharge that can't be read. The fuel line goes to review and is not paid.

**C. Carrier recommendation and guardrailed tender**
> "Recommend a carrier for load LGH0005494 and tender it."

The recommendation is the private fleet, expected $654, confidence 0.99, saving $351 and +23.5 pts
on-time vs the assigned Redline. `tender_load` returns AUTO_EXECUTED and logs it.
"Tender it to CR006 instead" pauses for approval (confidence below 80%, CONDITIONAL safety rating,
not the top choice). Approving or rejecting is logged too.

## 5. Expected business impact

Synthetic network: about 46 loads a day, about $6M a year of outside-carrier spend. The
assumptions are stated so they can be swapped for real volumes.

| Lever | Synthetic evidence (90 days) | Annualized (synthetic) | Assumption to validate |
|---|---|---|---|
| Freight audit recoveries | $15.8k overbilled, 1.06% of carrier spend | ~$64k | The overbilling rate on real bills. Measure on 3 months of history |
| Accessorial leakage (unbilled detention / lumper) | $83k recoverable, mostly BurgerBarn (26% detention capture) | ~$338k | Customer contracts allow detention billing at $75/hr after 2h |
| Unprofitable lane DC05→NV | −$61k margin, 48% empty miles | ~−$250k exposure | Backhaul or rate / minimum-charge fix recovers half |
| Reefer excursions on 9+ yr units | 17.6% excursion rate vs 0.6% on newer units, ~$595k est. product loss | Large: replace or repair the worst units first | The product-loss estimate per excursion |
| Restaurant early / late arrivals | Restaurant OTD 78.9% vs 94% target, 108 early misses in 28 days | Fewer refused deliveries and penalties | Restaurant receiving windows are enforced as in the data |
| Dwell creep at Fresh Basket | +27.7 min per stop | ~$151k a year of truck time at $85/hr | Truck-hour cost and the cause (dock staffing vs appointment mix) |
| Out-of-route miles (DC08) | ~13% OOR on four drivers vs ~2.5% fleet | Fuel and maintenance on the extra miles (see `get_out_of_route_miles`) | Odometer feed quality from the ELD provider |
| Carrier mix (Redline) | 71.8% on-time vs 86% private fleet, 60% tender acceptance | Fewer late penalties, fewer re-tenders | Capacity is available on the alternative carriers |
| Analyst / audit hours | 77% of invoices pass automatically, ~10 min manual review each | ~600 hours a year in freight audit, plus planner tendering time | Manual review time per invoice and per tender |

**Success metrics for a 90-day pilot:** audit catch rate on real bills, $ recovered, % of loads
auto-tendered with < 5% overrides, delay-prediction precision at the operating threshold, and planner
hours saved.

## Risks and next steps

- **Model drift and data quality**: retrain the delay model weekly (BQML), monitor AUC, and alert when
  `NEEDS_REVIEW` volume spikes.
- **Over-automation**: guardrails live in code and env config, not in prompts. Every action is logged.
  The TMW write stays simulated until approval roles are agreed.
- **NL-to-SQL safety**: use a read-only service account plus the SQL guard, cap BigQuery bytes billed
  (5 GB per query), and use a read-only transaction in AlloyDB.
- **Next**: Looker dashboards on the views, Pub/Sub check calls for real-time risk, a Vertex AI AutoML
  delay model, and an A2A handoff to the route optimization agent for re-planning.
