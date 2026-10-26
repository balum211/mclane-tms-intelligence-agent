#!/usr/bin/env bash
# One-time Google Cloud setup for TMS Intelligence. Review before running.
#   PROJECT_ID=my-proj REGION=us-central1 ./deployment/setup_gcp.sh [bigquery|alloydb|both]
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
TARGET="${1:-bigquery}"
DATASET="${DATASET:-mclane_tms}"
SA_NAME="tms-agent"
SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"
gcloud services enable aiplatform.googleapis.com bigquery.googleapis.com discoveryengine.googleapis.com \
  cloudbuild.googleapis.com run.googleapis.com logging.googleapis.com storage.googleapis.com

# Runtime identity for the agent: read-only on TMS data, write only to the decision log.
gcloud iam service-accounts create "$SA_NAME" --display-name "TMS Intelligence agent" || true
for role in roles/aiplatform.user roles/bigquery.jobUser roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$SA" --role "$role" --condition=None >/dev/null
done

python -m tms_data.generate --out data/generated

if [[ "$TARGET" == "bigquery" || "$TARGET" == "both" ]]; then
  python -m tms_data.load --target bigquery --project "$PROJECT_ID" --dataset "$DATASET" --location US
  # Dataset-level read access for the agent; the decision log table gets write access.
  bq add-iam-policy-binding --member="serviceAccount:$SA" --role=roles/bigquery.dataViewer "${PROJECT_ID}:${DATASET}" || \
    echo "Grant roles/bigquery.dataViewer on ${DATASET} to ${SA} in the console if this failed."
  bq add-iam-policy-binding --member="serviceAccount:$SA" --role=roles/bigquery.dataEditor \
    "${PROJECT_ID}:${DATASET}.agent_decision_log" || true
  bq query --use_legacy_sql=false --project_id="$PROJECT_ID" < <(sed "s/YOUR_PROJECT/${PROJECT_ID}/g" sql/bigquery_ml_delay_model.sql) || \
    echo "BigQuery ML model step skipped (optional)."
fi

if [[ "$TARGET" == "alloydb" || "$TARGET" == "both" ]]; then
  gcloud services enable alloydb.googleapis.com servicenetworking.googleapis.com compute.googleapis.com
  CLUSTER="${CLUSTER:-tms-cluster}"; INSTANCE="${INSTANCE:-tms-primary}"
  : "${ALLOYDB_PASSWORD:?set ALLOYDB_PASSWORD for the postgres user}"
  # Private services access on the default VPC (skip if already configured).
  gcloud compute addresses create alloydb-psa --global --purpose=VPC_PEERING --prefix-length=16 --network=default || true
  gcloud services vpc-peerings connect --service=servicenetworking.googleapis.com --ranges=alloydb-psa --network=default || true
  gcloud alloydb clusters create "$CLUSTER" --region="$REGION" --password="$ALLOYDB_PASSWORD" --network=default || true
  gcloud alloydb instances create "$INSTANCE" --cluster="$CLUSTER" --region="$REGION" --instance-type=PRIMARY \
    --cpu-count=2 --database-flags=google_columnar_engine.enabled=on || true
  echo "Start the AlloyDB Auth Proxy, then load:"
  echo "  ./alloydb-auth-proxy projects/${PROJECT_ID}/locations/${REGION}/clusters/${CLUSTER}/instances/${INSTANCE} &"
  echo "  python -m tms_data.load --target alloydb --dsn postgresql://postgres:\$ALLOYDB_PASSWORD@127.0.0.1:5432/postgres"
fi
echo "Done. Next: deployment/deploy_agent_engine.sh"
