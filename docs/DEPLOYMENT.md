# Deployment: BigQuery / AlloyDB, Agent Engine, Gemini Enterprise

## 1. Prerequisites

- A Google Cloud project with billing, plus `gcloud`, `bq` and Python 3.11+.
- `pip install -e ".[dev]"` from the repo root.
- `cp tms_agent/.env.example tms_agent/.env` and fill it in. `adk web`, `adk run` and `adk deploy` all read this file.

## 2. Data

```bash
PROJECT_ID=my-proj ./deployment/setup_gcp.sh bigquery   # or: alloydb | both
```

This enables the APIs, creates the `tms-agent` service account (Vertex AI user, BigQuery job user,
log writer), generates the synthetic data, loads it, and grants read-only dataset access plus write
access to `agent_decision_log`. It also builds the optional BigQuery ML delay model.

**BigQuery** (recommended with Agent Engine): set `TMS_DB_BACKEND=bigquery`, `TMS_BQ_PROJECT`,
`TMS_BQ_DATASET=mclane_tms`. Every agent query is capped at 5 GB billed and labelled
`app=tms-intelligence-agent`.

**AlloyDB**: `setup_gcp.sh alloydb` creates the cluster and primary instance (columnar engine on).
Load through the AlloyDB Auth Proxy:

```bash
./alloydb-auth-proxy projects/$PROJECT_ID/locations/us-central1/clusters/tms-cluster/instances/tms-primary &
python -m tms_data.load --target alloydb --dsn "postgresql://postgres:$ALLOYDB_PASSWORD@127.0.0.1:5432/postgres"
psql ... -c "CREATE ROLE tms_reader LOGIN PASSWORD '...'; GRANT USAGE ON SCHEMA tms TO tms_reader;
             GRANT SELECT ON ALL TABLES IN SCHEMA tms TO tms_reader;"
```

The agent opens every AlloyDB query in a `READ ONLY` transaction with a 30s statement timeout.
AlloyDB has private IPs only. Use Cloud Run with a VPC connector (section 4), or Agent Engine with
Private Service Connect.

## 3. Agent Engine (the runtime Gemini Enterprise calls)

```bash
PROJECT_ID=my-proj REGION=us-central1 ./deployment/deploy_agent_engine.sh
```

This wraps `adk deploy agent_engine ... tms_agent`. It stages `tms_agent/` with its `requirements.txt`
and `.env`, builds the image and prints the resource name
`projects/<p>/locations/<r>/reasoningEngines/<id>`. To update in place, re-run with `AGENT_ENGINE_ID=<id>`.

Smoke test from Python:

```python
import vertexai
client = vertexai.Client(project="my-proj", location="us-central1")
agent = client.agent_engines.get(name="projects/.../reasoningEngines/...")
for event in agent.stream_query(user_id="demo", message="Give me this morning's TMS brief."):
    print(event)
```

## 4. Cloud Run (alternative, includes the ADK web UI)

```bash
PROJECT_ID=my-proj ./deployment/deploy_cloud_run.sh
```

To reach AlloyDB, attach a Serverless VPC connector (the command is in the script).

## 5. Gemini Enterprise

The console route is **Gemini Enterprise → Apps → your app → Agents → Add agent → Custom agent via
Agent Engine**. Paste the reasoning engine resource name and the description from
`register_gemini_enterprise.sh`. The script does the same through the Discovery Engine API. Check
the current API version in the Gemini Enterprise docs before you use it.

Give business users `roles/discoveryengine.user` on the app. The agent runs as the `tms-agent`
service account, so users never get direct data access.

## 6. Guardrails and audit in production

| Setting | Default | Purpose |
|---|---|---|
| `TMS_AUTO_TENDER_MAX_USD` | 2500 | No auto-tender above this expected cost |
| `TMS_AUTO_TENDER_MIN_CONFIDENCE` | 0.80 | No auto-tender below this confidence |
| `TMS_DECISION_LOG_BQ_TABLE` | unset | Stream every decision to BigQuery |
| `TMS_DECISION_LOG_ALLOYDB_DSN` | unset | ...or to AlloyDB |

Decisions are always written to Cloud Logging as `event=tms_agent_decision`. Use a log-based metric
to alert when `PENDING_APPROVAL` items go unanswered.

## 7. Evaluate before you demo

```bash
pytest -q                                   # tools, guard, data stories, ADK runner, approval flow
python evals/run_offline_evals.py           # audit precision/recall + delay model card (no LLM)
adk eval tms_agent evals/tms_core.evalset.json --config_file_path evals/test_config.json   # needs Gemini
```
