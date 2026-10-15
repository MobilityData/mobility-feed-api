#!/bin/bash
#
#  MobilityData 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# Populates the local "users" database with dummy data for development
# and tests. Reads connection parameters from config/.env.local. The
# target DB defaults to "MobilityDatabaseUsers" (POSTGRES_USER_DB).
#
# Usage:
#   ./populate-db-test-data-users.sh
#
# Dependencies: docker (executes psql inside the running postgres container).

set -e

SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"
ENV_FILE="$SCRIPT_PATH/../config/.env.local"
SQL_FILE="$SCRIPT_PATH/../liquibase/test_data/users_test_data.sql"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Copy config/.env.local from the template first." >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

USER_DB="${POSTGRES_USER_DB:-MobilityDatabaseUsers}"
CONTAINER="database"
if [ "${USE_TEST_DB:-false}" = "true" ]; then
  CONTAINER="database_test"
fi

echo "Loading dummy users data into $CONTAINER / $USER_DB ..."
docker exec -i \
  -e PGPASSWORD="$POSTGRES_PASSWORD" \
  "$CONTAINER" \
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$USER_DB" < "$SQL_FILE"

echo "Done."
