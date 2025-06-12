#!/bin/bash
# This script is used by the duplicate-prod-db.yml workflow.
# It exports the PROD DB to a bucket, then imports it to the QA DB.
# It also makes a backup of the QA DB.

# Exit on any error
set -e

# Validate required environment variables
REQUIRED_VARS=(
  "DB_INSTANCE_NAME"
  "DUMP_BUCKET_NAME"
  "SOURCE_DATABASE_NAME"
  "DEST_DATABASE_NAME"
  "DEST_DATABASE_PASSWORD"
  "DEST_DATABASE_IMPORT_USER"
  "DUMP_FILE_NAME"
  "BACKUP_DB"

)

for VAR in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!VAR}" ]; then
    echo "Error: Environment variable $VAR is not set."
    exit 1
  fi
done

if [ "$BACKUP_DB" == "true" ]; then
  echo "Dump the QA database as a backup"
  # According to chatgpt,
  # This is Google's recommended, safe method and doesn’t require direct access to the DB. It runs the export
  # in a way that avoids locking the database and works from GCP itself (so no traffic leaves GCP).
  gcloud sql export sql $DB_INSTANCE_NAME gs://$DUMP_BUCKET_NAME/qa-db-dump-backup.sql --database=$SOURCE_DATABASE_NAME --quiet
else
  echo "Skipping backup of the QA database as it was not requested"
fi

echo "Deleting the existing $DEST_DATABASE_NAME database"
gcloud sql databases delete $DEST_DATABASE_NAME --instance=$DB_INSTANCE_NAME --quiet

echo "Recreating the $DEST_DATABASE_NAME database"
gcloud sql databases create $DEST_DATABASE_NAME --instance=$DB_INSTANCE_NAME

echo "Importing the dump into the QA database"
# The exported sql contains statements that require authentication as user postgres.
# In theory we could dump the DB without these statements, with:
# pg_dump --no-owner --no-privileges -d your_database > clean_dump.sql.

# The dumped DB refers to the PROD database user (data_feeds_user), so we need to be this user when importing.
export PGPASSWORD=$DEST_DATABASE_PASSWORD
gcloud sql import sql $DB_INSTANCE_NAME gs://$DUMP_BUCKET_NAME/$DUMP_FILE_NAME --database=$DEST_DATABASE_NAME --user=$DEST_DATABASE_IMPORT_USER --quiet

echo "Deleting the dump file from the bucket"
gsutil rm gs://$DUMP_BUCKET_NAME/$DUMP_FILE_NAME