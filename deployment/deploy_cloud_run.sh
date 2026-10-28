#!/usr/bin/env bash
# Alternative: run the agent (with the ADK web UI) on Cloud Run, e.g. to reach AlloyDB through a VPC connector.
#   PROJECT_ID=my-proj REGION=us-central1 ./deployment/deploy_cloud_run.sh
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
adk deploy cloud_run \
  --project "$PROJECT_ID" --region "$REGION" \
  --service_name tms-intelligence --app_name tms_agent --with_ui \
  --env TMS_DB_BACKEND="${TMS_DB_BACKEND:-bigquery}" \
  --env TMS_BQ_PROJECT="$PROJECT_ID" --env TMS_BQ_DATASET="${DATASET:-mclane_tms}" \
  --env GOOGLE_GENAI_USE_ENTERPRISE=True --env GOOGLE_GENAI_USE_VERTEXAI=True --env GOOGLE_CLOUD_PROJECT="$PROJECT_ID" \
  --env GOOGLE_CLOUD_LOCATION="${GEMINI_LOCATION:-global}" \
  tms_agent
# For AlloyDB add: --env TMS_DB_BACKEND=alloydb --env TMS_ALLOYDB_DSN=... and attach a Serverless VPC connector:
#   gcloud run services update tms-intelligence --region $REGION --vpc-connector <connector> --vpc-egress private-ranges-only
