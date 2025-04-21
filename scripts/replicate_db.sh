#!/bin/bash
# We should already be authenticated with gcloud when entering this script
set -x

# Define variables about GCP.
# For now we use the same DB instance for source and destination.
SOURCE_PROJECT_ID="mobility-feeds-qa"
DEST_PROJECT_ID=$SOURCE_PROJECT_ID
BUCKET_PROJECT_ID="mobility-feeds-dev"
BUCKET_NAME="mobilitydata-database-dump-dev2"
SOURCE_SQL_SERVICE_ACCOUNT="p563580583640-lc8lq4@gcp-sa-cloud-sql.iam.gserviceaccount.com"
DEST_SQL_SERVICE_ACCOUNT=$SOURCE_SQL_SERVICE_ACCOUNT
DEST_DATABASE_USER="postgres"
DEST_DATABASE_PASSWORD="...Put password here..."
SOURCE_DATABASE_NAME="MobilityDatabase"
DEST_DATABASE_NAME="MobilityDatabasePreRelease"
GCP_REGION="northamerica-northeast1"
SOURCE_DB_INSTANCE_NAME="mobilitydata-database-instance"
DEST_DB_INSTANCE_NAME=$SOURCE_DB_INSTANCE_NAME
DUMP_FILE_NAME="qa-db.sql"

echo "Service account: $SERVICE_ACCOUNT"

if ! gsutil ls -b "gs://${BUCKET_NAME}" &> /dev/null; then
  echo "Bucket doesn't exist. Creating..."
  gsutil mb -l $GCP_REGION -p $BUCKET_PROJECT_ID "gs://${BUCKET_NAME}"
else
  echo "Bucket already exists."
fi

# Give write permission for the source sql instance to write to the bucket
gsutil iam ch serviceAccount:$SOURCE_SQL_SERVICE_ACCOUNT:objectCreator gs://$BUCKET_NAME

# Give read permission on the bucket to the destination sql instance
gsutil iam ch serviceAccount:$DEST_SQL_SERVICE_ACCOUNT:objectViewer gs://$BUCKET_NAME

# Dump the db
# According to chatgpt,
# This is Google's recommended, safe method and doesn’t require direct access to the DB. It runs the export
# in a way that avoids locking the database and works from GCP itself (so no traffic leaves GCP).
gcloud sql export sql $SOURCE_DB_INSTANCE_NAME gs://$BUCKET_NAME/$DUMP_FILE_NAME --database=$SOURCE_DATABASE_NAME --project=$SOURCE_PROJECT_ID --quiet

# Create a new database
gcloud sql databases create $DEST_DATABASE_NAME --instance=$DEST_DB_INSTANCE_NAME

# Import to the new DB
# The exported sql contains statements that require authentication as user postgres.
# In theory we could dump the DB without these statements, with:
# pg_dump --no-owner --no-privileges -d your_database > clean_dump.sql.

export PGPASSWORD=$DEST_DATABASE_PASSWORD
gcloud sql import sql $DEST_DB_INSTANCE_NAME gs://$BUCKET_NAME/$DUMP_FILE_NAME --project=$DEST_PROJECT_ID --database=$DEST_DATABASE_NAME --user=$DEST_DATABASE_USER --quiet