#!/bin/bash
# This script is used by the duplicate-prod-db.yml workflow.
# It creates a bucket to house the dump of the production database.
# It also gives permission to the dump bucket so the SQL instances in PROD and QA can use it.

# Exit on any error
set -e

# Validate required environment variables
REQUIRED_VARS=(
  "DEST_PROJECT_ID"
  "DUMP_BUCKET_NAME"
  "GCP_REGION"
  "BUCKET_PROJECT_ID"
  "SOURCE_SQL_SERVICE_ACCOUNT"
  "DB_INSTANCE_NAME"
)

for VAR in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!VAR}" ]; then
    echo "Error: Environment variable $VAR is not set."
    exit 1
  fi
done

BUCKET_PROJECT_ID=$DEST_PROJECT_ID

echo "Checking if bucket exists..."
if ! gsutil ls -b "gs://${DUMP_BUCKET_NAME}" &> /dev/null; then
  echo "Bucket doesn't exist. Creating..."
  gsutil mb -l $GCP_REGION -p $BUCKET_PROJECT_ID "gs://${DUMP_BUCKET_NAME}"
else
  echo "Bucket already exists."
fi

echo "Giving permission for the source sql instance to read-write to the bucket"
gsutil iam ch serviceAccount:$SOURCE_SQL_SERVICE_ACCOUNT:objectAdmin gs://$DUMP_BUCKET_NAME

echo "Getting the service account for the QA DB to give permission to the bucket"
DEST_SQL_SERVICE_ACCOUNT=$(gcloud sql instances describe $DB_INSTANCE_NAME --format="value(serviceAccountEmailAddress)")
echo "Destination SQL Service Account: $DEST_SQL_SERVICE_ACCOUNT"

echo "Giving permission for the dest sql instance to read-write to the bucket"
gsutil iam ch serviceAccount:$DEST_SQL_SERVICE_ACCOUNT:objectAdmin gs://$DUMP_BUCKET_NAME
