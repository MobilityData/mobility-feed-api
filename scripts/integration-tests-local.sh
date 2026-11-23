#!/bin/bash
#
# Runs the integration tests locally the same way the PR workflow does (integration-tests-pr.yml),
# against the local TEST database (postgres-test), so the main local database is left untouched:
#   1. Rebuilds the test database from the branch's Liquibase changelogs.
#   2. Regenerates the API code (Feeds, User Service, Garage).
#   3. Seeds the test database from integration-tests/fixtures (integration-tests-seed-db.sh).
#   4. Starts the API on port 8080 against the test database, runs the tests and stops the API.
#
# The test database (./data-test) is the one the unit tests use; it is wiped on each full run.
# Run `scripts/docker-localdb-rebuild-data.sh --use-test-db` to get an empty one back for unit tests.
# Needs the variables of config/.env.local (POSTGRES_*), as docker-compose.yaml does.
#
# Usage: scripts/integration-tests-local.sh [options]
#   --csv <path>   Use this sources.csv instead of integration-tests/fixtures/sources.csv.
#   --skip-seed    Do not rebuild or seed the database; reuse the one from the previous run.
#   --skip-gen     Do not regenerate the API code.
#   -c <classes>   Comma-separated test classes to include.
#   -x <classes>   Comma-separated test classes to exclude (default: the metadata and smoke classes).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORK_DIR="${REPO_ROOT}/.integration-tests"
CACHED_CSV="${WORK_DIR}/sources.csv"
API_LOG="${WORK_DIR}/api_logs.txt"
API_URL="http://localhost:8080"

CSV_PATH=""
SKIP_SEED=false
SKIP_GEN=false
INCLUDE_CLASSES=""
# The metadata classes need api/src/version_info, which the PR workflow writes before its health
# check (extract-hash-and-version.sh fetches from origin). SmokeEndpointTests is for deployed APIs.
EXCLUDE_CLASSES="MetadataEndpointTests,BasicMetadataEndpointTests,SmokeEndpointTests"

print_help() {
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --csv) CSV_PATH="$(realpath "$2")"; shift 2 ;;
    --skip-seed) SKIP_SEED=true; shift ;;
    --skip-gen) SKIP_GEN=true; shift ;;
    -c) INCLUDE_CLASSES="$2"; shift 2 ;;
    -x) EXCLUDE_CLASSES="$2"; shift 2 ;;
    -h|--help) print_help 0 ;;
    *) echo "Unknown argument: $1" >&2; print_help 1 ;;
  esac
done

if lsof -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: port 8080 is already in use. Stop the running API first." >&2
  exit 1
fi

mkdir -p "${WORK_DIR}"

# Point every step at the test database. The values come from config/.env.local; variables set
# here take precedence over the env files the downstream scripts load (load_dotenv does not
# override, populate-licenses.sh keeps a caller-provided FEEDS_DATABASE_URL).
set -a
# shellcheck disable=SC1091
source "${REPO_ROOT}/config/.env.local"
set +a
DB_HOST="${POSTGRES_HOST:-localhost}"
export FEEDS_DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${DB_HOST}:${POSTGRES_TEST_PORT}/${POSTGRES_TEST_DB}"
export USERS_DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${DB_HOST}:${POSTGRES_TEST_PORT}/${POSTGRES_USER_TEST_DB:-MobilityDatabaseUsersTest}"
export USE_TEST_DB=true # read by db-gen.sh and db-gen-user.sh
export ENVIRONMENT=local # never publish to Pub/Sub while seeding

COMPOSE=(docker compose --env-file "${REPO_ROOT}/config/.env.local" -f "${REPO_ROOT}/docker-compose.yaml")
USERS_TEST_DB="${POSTGRES_USER_TEST_DB:-MobilityDatabaseUsersTest}"

# Whether the test database finished its first-start initialization: it accepts TCP connections
# (the temporary server the image runs during init does not) and the users database created by
# liquibase/init exists.
test_db_ready() {
  docker exec database_test pg_isready -q -h 127.0.0.1 -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" 2>/dev/null \
    && [[ "$(docker exec database_test psql -U "${POSTGRES_USER}" -d "${POSTGRES_TEST_DB}" -tAc \
      "SELECT 1 FROM pg_database WHERE datname = '${USERS_TEST_DB}'" 2>/dev/null)" == "1" ]]
}

# Recreates the test database from scratch and applies the Liquibase changelogs. On Docker Desktop
# for Mac the first start on the ./data-test bind mount can fail ("data directory has wrong
# ownership"), leaving a server without the init scripts' databases, so a failed initialization
# is detected and the clean start retried instead of being slept past.
rebuild_test_db() {
  local attempt
  for attempt in 1 2 3; do
    echo "INFO: Starting a clean test database (attempt ${attempt}/3)"
    # container_name is fixed, so a container left by another checkout's compose project would
    # block this one.
    docker rm -f database_test >/dev/null 2>&1 || true
    rm -rf "${REPO_ROOT}/data-test"
    "${COMPOSE[@]}" up -d postgres-test
    for _ in $(seq 1 60); do
      test_db_ready && break
      if [[ "$(docker inspect -f '{{.State.Running}}' database_test 2>/dev/null)" != true ]]; then
        break
      fi
      sleep 2
    done
    if test_db_ready; then
      echo "INFO: Applying the Liquibase changelogs to the test databases"
      "${COMPOSE[@]}" run --rm liquibase-test
      "${COMPOSE[@]}" run --rm liquibase-user-test
      return 0
    fi
    echo "WARNING: the test database did not initialize; last log lines:" >&2
    docker logs --tail 5 database_test >&2 || true
  done
  echo "ERROR: the test database failed to initialize 3 times." >&2
  exit 1
}

if [[ "${SKIP_SEED}" == true ]]; then
  # The tests must read the same file the database was seeded from.
  if [[ -z "${CSV_PATH}" ]]; then
    if [[ ! -f "${CACHED_CSV}" ]]; then
      echo "ERROR: --skip-seed needs a previous seeded run (${CACHED_CSV} not found)." >&2
      exit 1
    fi
    CSV_PATH="${CACHED_CSV}"
  fi
  if ! docker ps --format '{{.Names}}' | grep -qx database_test; then
    echo "ERROR: the database_test container is not running. Run without --skip-seed." >&2
    exit 1
  fi
else
  CSV_PATH="${CSV_PATH:-${REPO_ROOT}/integration-tests/fixtures/sources.csv}"
  if [[ "${CSV_PATH}" != "${CACHED_CSV}" ]]; then
    cp "${CSV_PATH}" "${CACHED_CSV}"
  fi
  CSV_PATH="${CACHED_CSV}"

  echo "INFO: Rebuilding the local test database"
  rebuild_test_db
fi

if [[ "${SKIP_GEN}" != true ]]; then
  echo "INFO: Generating the API code"
  "${SCRIPT_DIR}/db-gen.sh"
  "${SCRIPT_DIR}/db-gen-user.sh"
  "${SCRIPT_DIR}/api-gen.sh"
  "${SCRIPT_DIR}/api-user-service-gen.sh"
  "${SCRIPT_DIR}/api-garage-gen.sh"
fi

if [[ "${SKIP_SEED}" != true ]]; then
  "${SCRIPT_DIR}/integration-tests-seed-db.sh" "${CSV_PATH}"
fi

echo "INFO: Starting the API against the test database (logs: ${API_LOG})"
"${SCRIPT_DIR}/api-start.sh" >"${API_LOG}" 2>&1 &
API_PID=$!
stop_api() {
  # api-start.sh runs uvicorn in a subshell; stop it and its children.
  pkill -P "${API_PID}" 2>/dev/null || true
  pkill -f "uvicorn main:app --host 0.0.0.0 --port 8080" 2>/dev/null || true
  kill "${API_PID}" 2>/dev/null || true
}
trap stop_api EXIT

for i in $(seq 1 60); do
  if curl -sf -o /dev/null "${API_URL}/v1/metadata"; then
    echo "INFO: API is up after ${i}s"
    break
  fi
  if [[ "${i}" -eq 60 ]]; then
    echo "ERROR: API did not start within 60s" >&2
    tail -n 50 "${API_LOG}" >&2
    exit 1
  fi
  sleep 1
done

test_args=(-u "${API_URL}" -f "${CSV_PATH}")
[[ -n "${INCLUDE_CLASSES}" ]] && test_args+=(-c "${INCLUDE_CLASSES}")
[[ -n "${EXCLUDE_CLASSES}" ]] && test_args+=(-x "${EXCLUDE_CLASSES}")

DUMMY_TOKEN=DUMMY_TOKEN "${SCRIPT_DIR}/integration-tests.sh" "${test_args[@]}"
