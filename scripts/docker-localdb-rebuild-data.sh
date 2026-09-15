#!/bin/bash
#
#
#  MobilityData 2024
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This script deletes the data and the local database container.
# Then it downloads the latest csv file and populates the database applying the liquibase changes.
# Usage:
#       ./docker-localdb-rebuild-data.sh --populate-db
# Options:
#       --populate-db: populate the database with the latest csv file
# Dependencies:
#      docker, docker-compose, wget

target_csv_file="catalogs.csv"
# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

display_usage() {
  printf "\nThis script deletes the data and the local database container.\n"
  printf "\nScript Usage:\n"
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  --populate-db <TEST_FILE> Populate the database with the latest csv file."
  echo "  --populate-test-data      Populate the database with the test data."
  echo "  --use-test-db             Populate the test database."
  echo "  --help                    Display help content."
  exit 1
}

POPULATE_DB=false
POPULATE_TEST_DATA=false
USE_TEST_DB=false
while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
  --help)
    display_usage
    ;;
  --populate-db)
    POPULATE_DB=true
    shift # past argument
    ;;
  --populate-test-data)
    POPULATE_TEST_DATA=true
    shift # past argument
    ;;
  --use-test-db)
    export USE_TEST_DB=true
    shift # past argument
    ;;
  *)      # unknown option
    shift # past argument
    ;;
  esac
done

# Per-worktree Compose project and host ports, so this stack can run alongside
# other worktrees'. Generates config/.env.worktree on first use.
# shellcheck source=./worktree-env.sh
source "$SCRIPT_PATH/worktree-env.sh" --ensure

db_service="postgres"
docker_service="liquibase"
docker_service_user="liquibase-user"
data_volume="pgdata"

if [ "$USE_TEST_DB" = true ]; then
    db_service="postgres-test"
    docker_service="liquibase-test"
    docker_service_user="liquibase-user-test"
    data_volume="pgdata_test"
fi

worktree_env_compose_args
compose() { docker compose "${WORKTREE_COMPOSE_ARGS[@]}" "$@"; }

# Stop and remove this worktree's DB container, then drop its data volume.
# Scoped to this Compose project only - other worktrees are untouched.
compose rm --stop --force "$db_service"
docker volume rm --force "${COMPOSE_PROJECT_NAME:-mobility-feed-api}_${data_volume}" >/dev/null 2>&1

# Start the database and block until it actually accepts TCP connections.
if ! compose up -d --wait "$db_service"; then
  printf "\n---------\nFailure: %s did not become healthy.\n---------\n" "$db_service"
  compose logs --tail 40 "$db_service"
  exit 1
fi

# Apply the migrations as one-shot jobs. `run --rm` surfaces liquibase's real
# exit code (and ignores the restart policy), so a failed migration stops the
# script here instead of silently leaving an unmigrated DB for db-gen.sh.
for service in "$docker_service" "$docker_service_user"; do
  if ! compose run --rm "$service"; then
    printf "\n---------\nFailure: liquibase service '%s' failed.\n---------\n" "$service"
    exit 1
  fi
done

# generate the models
$SCRIPT_PATH/db-gen.sh
$SCRIPT_PATH/db-gen-user.sh


if [ "$POPULATE_DB" = true ]; then
    # download the latest csv file and populate the db
    mkdir -p $SCRIPT_PATH/../data/
    wget -O $SCRIPT_PATH/../data/$target_csv_file https://storage.googleapis.com/storage/v1/b/mdb-csv/o/sources.csv?alt=media
    # populate licenses before feeds so that feed.license_id FK references are satisfied
    $SCRIPT_PATH/populate-licenses.sh
    printf "\n---------\nCompleted: populating license data.\n---------\n"
    # populate db
    full_path="$(readlink -f $SCRIPT_PATH/../data/$target_csv_file)"
    $SCRIPT_PATH/populate-db.sh $full_path
    printf "\n---------\nCompleted: populating catalog data.\n---------\n"
fi

if [ "$POPULATE_TEST_DATA" = true ]; then
    # populate test data
    $SCRIPT_PATH/populate-db-test-data.sh
    printf "\n---------\nCompleted: populating test data.\n---------\n"
    # populate dummy user test data into the users DB
    $SCRIPT_PATH/populate-db-test-data-users.sh
    printf "\n---------\nCompleted: populating users test data.\n---------\n"
fi

printf "\n---------\nSuccess: Rebuilding the database.\n---------\n"
