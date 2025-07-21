#!/bin/bash
# This script is used by the duplicate-prod-db.yml workflow.
# It execute some SQL scripts on the imported DBL
#   - Give permission to the tables to the postgres user.
#   - Modify the email addresses in the DB so we can't accidentally email real people.

# Exit on any error
set -e

# Validate required environment variables
REQUIRED_VARS=(
  "GCP_FEED_BASTION_SSH_KEY"
  "DEST_PROJECT_ID"
  "GCP_REGION"
  "GCP_FEED_BASTION_NAME"
  "GCP_FEED_SSH_USER"
  "DB_INSTANCE_NAME"
  "DEST_DATABASE_PASSWORD"
  "DEST_DATABASE_IMPORT_USER"
  "DEST_DATABASE_NAME"
)

for VAR in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!VAR}" ]; then
    echo "Error: Environment variable $VAR is not set."
    exit 1
  fi
done

echo "Tunelling"
mkdir -p ~/.ssh
echo "$GCP_FEED_BASTION_SSH_KEY" > ~/.ssh/id_rsa
chmod 600 ~/.ssh/id_rsa
./scripts/tunnel-create.sh -project_id $DEST_PROJECT_ID -zone ${GCP_REGION}-a -instance ${GCP_FEED_BASTION_NAME}-qa -target_account ${GCP_FEED_SSH_USER} -db_instance ${DB_INSTANCE_NAME} -port 5454
sleep 10 # Wait for the tunnel to establish

echo "Giving new role to postgres user"
export PGPASSWORD=$DEST_DATABASE_PASSWORD
psql -h localhost -p 5454 -U $DEST_DATABASE_IMPORT_USER -d $DEST_DATABASE_NAME -c "GRANT data_feeds_user TO postgres;"

echo "Redirecting email addresses to mobilitydata.org"
cat <<'EOF' | psql -h localhost -p 5454 -U postgres -d $DEST_DATABASE_NAME
  UPDATE feed
  SET feed_contact_email = REPLACE(feed_contact_email, '@', '_at_') || '@mobilitydata.org'
  WHERE feed_contact_email IS NOT NULL
    AND TRIM(feed_contact_email) <> '';
EOF