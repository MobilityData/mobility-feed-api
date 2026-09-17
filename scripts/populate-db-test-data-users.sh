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

# Per-worktree Compose project, so this targets this worktree's stack.
# shellcheck source=./worktree-env.sh
source "$SCRIPT_PATH/worktree-env.sh"
worktree_env_compose_args

USER_DB="${POSTGRES_USER_DB:-MobilityDatabaseUsers}"
DB_SERVICE="postgres"
if [ "${USE_TEST_DB:-false}" = "true" ]; then
  USER_DB="${POSTGRES_USER_TEST_DB:-MobilityDatabaseUsersTest}"
  DB_SERVICE="postgres-test"
fi

# Addressed by Compose *service* name, not container name: container names are
# project-prefixed so that several worktrees can run their stacks at once.
echo "Loading dummy users data into $DB_SERVICE / $USER_DB ..."
docker compose "${WORKTREE_COMPOSE_ARGS[@]}" exec -T \
  -e PGPASSWORD="$POSTGRES_PASSWORD" \
  "$DB_SERVICE" \
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$USER_DB" < "$SQL_FILE"

echo "Done."
