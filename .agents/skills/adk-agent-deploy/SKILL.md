---
name: adk-agent-deploy
description: Deploy the tms_agent ADK agent to Vertex AI Agent Engine or Cloud Run and register it in Gemini Enterprise, including BigQuery / AlloyDB setup, service account IAM and smoke tests. Use when the user asks to deploy, update, test in the cloud, or share the agent with business users.
---

# Deploy tms_agent

Full guide: `docs/DEPLOYMENT.md`. Never print or commit secrets; they belong in `tms_agent/.env`
(gitignored) or Secret Manager.

## Steps

1. **Pre-flight**: `uv run pytest -q` passes; `gcloud config get-value project` is the target project;
   `tms_agent/.env` exists (copy `.env.example`) with `GOOGLE_GENAI_USE_ENTERPRISE=True`,
   `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION=global` and the data backend settings (plus
   `PCMILER_API_KEY` if live PC*MILER miles are wanted). Optionally `uv run python server.py` and
   `curl localhost:8080/list-apps` to check the same app Cloud Run will serve.
2. **Data + IAM**: `PROJECT_ID=<p> ./deployment/setup_gcp.sh bigquery` (or `alloydb`, `both`).
   It enables APIs, creates the `tms-agent` service account with read-only data access and
   write access only to `agent_decision_log`, loads the synthetic data and trains the BQML model.
3. **Agent Engine**: `PROJECT_ID=<p> REGION=us-central1 ./deployment/deploy_agent_engine.sh`.
   It runs `adk deploy agent_engine --project --region --display_name ... tms_agent`. Save the
   printed `projects/.../reasoningEngines/<id>`. Re-run with `AGENT_ENGINE_ID=<id>` to update.
4. **Smoke test** (Python):
   ```python
   import vertexai
   client = vertexai.Client(project=PROJECT, location="us-central1")
   agent = client.agent_engines.get(name=RESOURCE)
   for e in agent.stream_query(user_id="smoke", message="Give me this morning's TMS brief."):
       print(e)
   ```
5. **Gemini Enterprise**: console path Gemini Enterprise → Apps → your app → Agents → Add agent →
   Custom agent via Agent Engine, or `./deployment/register_gemini_enterprise.sh` (check the current
   API version in the docs first). Grant users `roles/discoveryengine.user`.
6. **Alternative**: `./deployment/deploy_cloud_run.sh` (ADK web UI included; needed with a VPC
   connector for AlloyDB private IP).

## Guardrails in production

Keep `TMS_AUTO_TENDER_MAX_USD` and `TMS_AUTO_TENDER_MIN_CONFIDENCE` in the deployed `.env`. Set
`TMS_DECISION_LOG_BQ_TABLE` so every decision lands in BigQuery, and add a log-based alert on
unanswered `PENDING_APPROVAL` decisions.
