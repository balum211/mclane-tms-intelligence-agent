#!/usr/bin/env bash
# Deploy TMS Intelligence to Vertex AI Agent Engine (managed runtime used by Gemini Enterprise).
#   PROJECT_ID=my-proj REGION=us-central1 ./deployment/deploy_agent_engine.sh
# Reads tms_agent/.env for runtime env vars and tms_agent/requirements.txt for dependencies.
# For Agent Engine use TMS_DB_BACKEND=bigquery (AlloyDB needs Private Service Connect networking).
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SA="${SA:-tms-agent@${PROJECT_ID}.iam.gserviceaccount.com}"

if ! grep -q "^TMS_DB_BACKEND=bigquery" tms_agent/.env 2>/dev/null; then
  echo "WARNING: tms_agent/.env should set TMS_DB_BACKEND=bigquery for Agent Engine." >&2
fi

adk deploy agent_engine \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --display_name "TMS Intelligence" \
  --description "Trimble TMW intelligence: carrier selection, delay prediction, freight audit, NL-to-SQL" \
  --service_account "$SA" \
  ${AGENT_ENGINE_ID:+--agent_engine_id "$AGENT_ENGINE_ID"} \
  tms_agent

echo "Copy the reasoningEngines/<ID> resource name printed above into deployment/register_gemini_enterprise.sh"
