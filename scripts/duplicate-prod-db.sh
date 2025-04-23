#!/bin/bash
BUCKET_PROJECT_ID=$DEST_PROJECT_ID
DUMP_BUCKET_NAME="mobilitydata-database-dump-qa"
#
#echo "Key:"
#echo "$SOURCE_GCP_MOBILITY_FEEDS_SA_KEY" | sed 's/./&./g'

SOURCE_TEMP_KEY_FILE=$(mktemp)
DEST_TEMP_KEY_FILE=$(mktemp)

echo "$SOURCE_GCP_MOBILITY_FEEDS_SA_KEY" > $SOURCE_TEMP_KEY_FILE
gcloud config configurations create source-config
gcloud auth activate-service-account --key-file=$SOURCE_TEMP_KEY_FILE
gcloud config set project $SOURCE_PROJECT_ID

echo "$DEST_GCP_MOBILITY_FEEDS_SA_KEY" > $DEST_TEMP_KEY_FILE
gcloud config configurations create dest-config
gcloud auth activate-service-account --key-file=$DEST_TEMP_KEY_FILE
gcloud config set project $DEST_PROJECT_ID

gcloud config configurations activate source-config

SOURCE_SQL_SERVICE_ACCOUNT=$(gcloud sql instances describe "mobilitydata-database-instance" --project=$SOURCE_PROJECT_ID --format="value(serviceAccountEmailAddress)")

gcloud config configurations activate dest-config

if ! gsutil ls -b "gs://${DUMP_BUCKET_NAME}" &> /dev/null; then
    echo "Bucket doesnt exist. Creating..."
    gsutil mb -l $GCP_REGION -p $DEST_PROJECT_ID "gs://${DUMP_BUCKET_NAME}"
else
    echo "Bucket already exists."
fi