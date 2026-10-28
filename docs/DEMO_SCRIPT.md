# 5-minute demo script

Setup: `uv run adk web .` (local DuckDB) or the agent in Gemini Enterprise (BigQuery). The dataset as-of
date is 2026-10-27. Numbers below are from the default synthetic dataset, so expect the same values.

| Time | Say / type | What the audience sees | Before → after KPI |
|---|---|---|---|
| 0:00 | "Planners, freight audit and procurement each live in different TMW screens. TMS Intelligence answers all of them in one conversation, and it only acts inside guardrails." | | |
| 0:20 | **"Give me this morning's TMS brief."** | KPIs vs last week (on-time 85%, Retail OTD 87% vs Restaurant 80%, margin 14%, cost/mile $2.55), 39 loads in transit, 6 critical exceptions, Redline flagged, $83k of unbilled accessorials | One question instead of 5 reports |
| 1:00 | **"Which loads departing in the next 24 hours are likely to be late?"** | 16 of 48 loads flagged. The top ones are on Redline with 7+ stops and a high-risk receiver (p ≈ 0.70). Each comes with mitigations | Exceptions handled before dispatch, not after |
| 1:40 | **"Recommend a carrier for LGH0005494 and tender it."** | Private fleet recommended, $654 expected, confidence 0.99, saves $351 and +23.5 pts on-time vs Redline. `tender_load` → AUTO_EXECUTED (logged) | Planner touch time → 0 for in-policy loads |
| 2:20 | **"Actually, tender it to CR006."** | ADK pauses for approval: confidence below 80%, CONDITIONAL safety rating, not the top choice. Click reject. The decision log shows PENDING_APPROVAL → REJECTED | Shows safe autonomy |
| 3:00 | **"How much are carriers overbilling us?"** | 152 of 1,189 invoices, $15.8k (1.06% of spend), about $64k annualized. Redline is the largest at $8.5k. Breakdown by finding | Audit catch rate on planted errors: 100% |
| 3:30 | **"Audit data/sample_invoices/03_scanned_detention_illegible_fuel_CINV0000072.pdf"** | Gemini reads the scan. $162.50 detention with 0 minutes evidenced → DETENTION_NO_EVIDENCE. The fuel line is illegible → NEEDS_REVIEW (flagged, not guessed) | |
| 3:50 | **"How is Retail vs Restaurant on-time delivery, and where did dwell time change?"** | Retail OTD 84.6% vs Restaurant 78.9% (28 days), 108 restaurant arrivals more than 15 min early, DC07 worst at 71.0%. Fresh Basket Grocers dwell up +27.7 min (~$151k a year), Cluck & Co down −16.1 min | McLane OTD rules applied per channel, not one blended number |
| 4:10 | **"Which stops have geofence problems, and is anyone driving out of route?"** | 92.1% auto-arrival; STR00289 is a ZIP centroid 1,988 m off, with a corrected point from stopped ELD pings. Four DC08 drivers run ~13% over PC*MILER practical miles | Bad geocodes fixed at the source, OOR coached |
| 4:20 | **"How many stops did we deliver to TacoTrail last week and what was the average dwell?"** | NL-to-SQL: 78 stops, 61.8 min average dwell, with the SQL shown | Ad-hoc question answered in seconds instead of an analyst ticket |
| 4:30 | **"Give me the weekly insights."** | Ranked savings: BurgerBarn detention billing, the DC05→NV lane fix, shifting Redline volume, reefer unit replacement, freight audit recoveries | |
| 5:00 | Close: "Every recommendation shows reasoning, data, confidence and dollar impact, and every action is in the audit log." | `get_decision_log` | |

Backup questions: "Why is DC03 late on Mondays?" (50.3% Monday on-time, late dispatch), "Are reefer
excursions related to equipment age?" (17.6% vs 0.6%), "What's our least profitable lane?" (DC05→NV, −20%),
"Where is LGH0005479 and will it make its next window?" (`track_load`: last ping, PC*MILER or estimated
miles to go, ETA), "Check the PC*MILER miles on a carrier bill" (`check_pcmiler_miles`: billed vs
practical, MILES_INFLATED above 2%).
