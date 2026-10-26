#!/usr/bin/env bash
# Register the deployed Agent Engine agent in a Gemini Enterprise app so business users can chat with it.
# Console alternative: Gemini Enterprise > Apps > <your app> > Agents > Add agent > Custom agent via Agent Engine.
# API shape per the Gemini Enterprise (Discovery Engine) docs at the time of writing; verify before use.
#   PROJECT_ID=my-proj PROJECT_NUMBER=123 APP_ID=my-ge-app REASONING_ENGINE=projects/my-proj/locations/us-central1/reasoningEngines/456 \
#   ./deployment/register_gemini_enterprise.sh
set -euo pipefail
: "${PROJECT_ID:?}"; : "${PROJECT_NUMBER:?}"; : "${APP_ID:?Gemini Enterprise app (engine) id}"; : "${REASONING_ENGINE:?}"
GE_LOCATION="${GE_LOCATION:-global}"
HOST="discoveryengine.googleapis.com"
[[ "$GE_LOCATION" != "global" ]] && HOST="${GE_LOCATION}-discoveryengine.googleapis.com"

curl -sS -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "https://${HOST}/v1alpha/projects/${PROJECT_NUMBER}/locations/${GE_LOCATION}/collections/default_collection/engines/${APP_ID}/assistants/default_assistant/agents" \
  -d @- <<JSON
{
  "displayName": "TMS Intelligence",
  "description": "Ask about carriers, late loads, freight invoices, lane margins and fuel recovery over Trimble TMW data.",
  "icon": {"uri": "https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/local_shipping/default/24px.svg"},
  "adk_agent_definition": {
    "tool_settings": {
      "tool_description": "TMS Intelligence answers transportation questions (on-time, carriers, tenders, freight audit, lane profitability, delay risk) using the company TMS warehouse, and can recommend or tender carriers within guardrails."
    },
    "provisioned_reasoning_engine": {"reasoning_engine": "${REASONING_ENGINE}"}
  }
}
JSON
echo
echo "Grant end users roles/discoveryengine.user on the app; the agent runs as the Agent Engine service account."
