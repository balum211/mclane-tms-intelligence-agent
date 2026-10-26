---
trigger: always_on
---

# Project context: TMS Intelligence (Trimble TMW) on Google ADK

- Domain: US grocery / foodservice distribution. 8 DCs deliver to convenience stores, grocery and
  QSR / casual-dining restaurants. Trimble TMW is the TMS of record (orderheader, legheader, stops,
  carrier, paydetail, checkcall). Our tables keep that shape under readable names (`docs/DATA_STORY.md`).
- Stack: Python 3.11+, `google-adk`, Gemini on Vertex AI (`GOOGLE_GENAI_USE_ENTERPRISE=1`),
  BigQuery or AlloyDB (PostgreSQL) via `tms_agent/db.py`, DuckDB for local tests.
- Agent package: `tms_agent/` (`root_agent` in `agent.py`). Deploy target: Vertex AI Agent Engine,
  surfaced in Gemini Enterprise.
- Always follow `AGENTS.md` and `.specify/memory/constitution.md`.
- Before claiming a task is done, run `pytest -q` and report the result.
- Business guardrails: no auto-action above $2,500 or below 80% confidence without human approval;
  every decision is logged; messy inputs are flagged, never guessed.
- Prefer the project skills in `.agents/skills/` for SQL questions, invoice audits, data generation,
  tool authoring and deployment.
