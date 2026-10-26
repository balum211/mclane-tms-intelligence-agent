# Feature Specification: TMS Intelligence layer for Trimble TMW

**Feature Branch**: `001-tms-intelligence`
**Created**: 2026-10-26
**Status**: Implemented
**Input**: "Design an AI TMS Intelligence layer on top of the TMS that (1) recommends the best carrier per
load and auto-tenders within guardrails, (2) predicts delays 24h ahead and suggests mitigation, (3) audits
freight invoices against contracted rates and accessorial rules, (4) answers natural-language questions
with SQL-backed answers, (5) produces weekly insights. Every recommendation shows reasoning, data used,
confidence and $ impact. No auto-action above $X or confidence < 80% without human approval. Log all
decisions. Handle messy inputs: flag, don't guess."

## User Scenarios & Testing

### User Story 1 - Ask the TMS anything (Priority: P1)
A transportation planner asks a question in plain English ("Which lanes lost money last month?") and
gets a short answer with a table, the root cause, and the SQL or tool used.

**Independent Test**: Ask the 10 questions in `evals/tms_core.evalset.json`. Each routes to the right specialist.

**Acceptance Scenarios**:
1. **Given** the dataset, **When** the user asks "What is our least profitable lane?", **Then** the answer names DC05→NV with negative margin and high empty miles.
2. **Given** an ad-hoc question, **When** no curated tool fits, **Then** tms_data_analyst runs one read-only SELECT and shows the SQL.
3. **Given** a request to DELETE data, **When** SQL is generated, **Then** the guard rejects it.

### User Story 2 - Audit carrier freight bills (Priority: P1)
Freight audit sees which invoices are overbilled, by how much and why, and can draft a dispute.

**Acceptance Scenarios**:
1. **Given** carrier invoices, **When** audited, **Then** each overbilled invoice has a reason code, evidence and $ amount, and precision/recall vs planted errors are ≥ 95% / 90%.
2. **Given** a scanned invoice with an illegible fuel surcharge, **When** audited, **Then** it is NEEDS_REVIEW with the reason, and no value is guessed.
3. **Given** a spot load with no contract, **When** audited, **Then** the rate is flagged NO_CONTRACT_RATE while miles/fuel/detention/lumper are still checked.

### User Story 3 - Choose and tender the best carrier safely (Priority: P1)
A planner asks for the best carrier for a load. The agent recommends one with reasoning, confidence
and $ impact, and tenders automatically only within guardrails.

**Acceptance Scenarios**:
1. **Given** a planned load, **When** a recommendation is requested, **Then** it includes expected cost and its basis (contract / spot / private fleet), confidence, impact vs the current carrier and the guardrail result.
2. **Given** cost > cap or confidence < 80% or a CONDITIONAL carrier, **When** tender_load is called, **Then** the ADK runner emits a confirmation request and nothing executes until approved.
3. **Given** a completed load, **When** tender_load is called, **Then** it is BLOCKED and logged.

### User Story 4 - See tomorrow's late loads before dispatch (Priority: P2)
Dispatch sees loads departing in the next 24h ranked by late probability, with drivers and mitigations.

**Acceptance Scenarios**:
1. **Given** planned loads, **When** predictions run, **Then** each flagged load has probability, confidence, top drivers and a mitigation.
2. **Given** a 14-day time-based holdout, **When** the model card runs, **Then** AUC > 0.6 and top-decile lift > 1.1.

### User Story 5 - Weekly insights for leadership (Priority: P3)
A single request returns KPIs vs the prior week, worst lanes, carrier flags, audit savings, accessorial
leakage, spot premium and tomorrow's risk, as a ranked savings narrative.

### Edge Cases
- Tool or database error → the structured `error_message` is shown; the agent does not fabricate.
- Low sample size carriers → LOW_SAMPLE_SIZE flag; the recommendation confidence drops.
- No private fleet drivers free → the private fleet is excluded from recommendations.
- Missing DOE price for a week → NO_FUEL_INDEX review flag.

## Requirements

### Functional Requirements
- **FR-001**: Answer NL questions via curated tools or guarded NL-to-SQL over BigQuery, AlloyDB or DuckDB.
- **FR-002**: Recommend a carrier per load using on-time, expected cost, acceptance, safety and capacity.
- **FR-003**: Auto-tender only within `TMS_AUTO_TENDER_MAX_USD` and `TMS_AUTO_TENDER_MIN_CONFIDENCE`; otherwise request human approval.
- **FR-004**: Predict late loads departing in the next N hours with explanations and mitigations.
- **FR-005**: Audit carrier invoices with 8 rules and flag data gaps as NEEDS_REVIEW.
- **FR-006**: Extract scanned invoice fields with Gemini (null when illegible) and audit them.
- **FR-007**: Log every tender and dispute decision with rationale, evidence, confidence, amount and actor.
- **FR-008**: Produce a weekly insights pack.
- **FR-009**: Every recommendation shows reasoning, data used, confidence and $ impact.

### Key Entities
Customers, locations, carriers, drivers, tractors, trailers, orders, loads, stops, load_costs, invoices,
carrier_tenders, carrier_rates, carrier_invoices, check_calls, exceptions, fuel_prices, agent_decision_log
(see `data-model.md`).

## Success Criteria
- **SC-001**: All tool tests pass offline (DuckDB) and on PostgreSQL.
- **SC-002**: Invoice audit precision ≥ 95% and recall ≥ 90% on planted errors.
- **SC-003**: Delay model holdout AUC > 0.6.
- **SC-004**: Zero auto-tenders above the cap or below the confidence threshold.
- **SC-005**: The 5-minute demo script runs end to end in `adk web` and Gemini Enterprise.
