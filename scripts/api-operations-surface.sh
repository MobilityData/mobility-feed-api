#!/usr/bin/env bash
#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#
# api-operations-surface.sh
# ------------------------------------------------------------------------------
# Starts the Operations API against the local test database and hits EVERY
# endpoint over HTTP, asserting each returns an expected, non-5xx status.
#
# Why: the generated FastAPI routers call the impl methods WITHOUT `await`, so a
# route method that is accidentally declared `async` returns an un-awaited
# coroutine and fails at runtime with HTTP 500 (ResponseValidationError). The
# unit tests call the impls directly (and await them), so they never catch this.
# This suite crosses the real request -> router -> impl -> serialize path, so any
# such wiring/serialization regression turns into a failing endpoint here.
#
# Usage (runs from anywhere):
#   scripts/api-operations-surface.sh                 # start local server + test DB, run
#   scripts/api-operations-surface.sh --url <URL>     # hit an already-running API (post-deploy smoke)
#   scripts/api-operations-surface.sh --no-docker     # DB already up/migrated; don't touch docker
#   scripts/api-operations-surface.sh --keep-up       # leave the server running afterwards
#   scripts/api-operations-surface.sh --port 8099
# ------------------------------------------------------------------------------
set -euo pipefail

# --- resolve paths relative to this script so it works from any CWD -----------
SCRIPT_PATH="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_PATH/.." && pwd)"
OPS_DIR="$ROOT/functions-python/operations_api"

PORT=8095
BASE_URL=""
USE_DOCKER=1
KEEP_UP=0
SERVER_PID=""

usage() {
  sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url) BASE_URL="$2"; USE_DOCKER=0; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --no-docker) USE_DOCKER=0; shift ;;
    --keep-up) KEEP_UP=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown argument: $1" >&2; usage 1 ;;
  esac
done

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }; }
need curl
need jq

# --- provision + start the server (unless hitting an external --url) ----------
if [[ -z "$BASE_URL" ]]; then
  need python3

  # 1. Generated OpenAPI stubs (routers/models the app imports).
  if [[ ! -d "$OPS_DIR/src/feeds_gen" ]]; then
    [[ -x "$ROOT/scripts/bin/openapitools/openapi-generator-cli" ]] || "$ROOT/scripts/setup-openapi-generator.sh"
    "$ROOT/scripts/api-operations-gen.sh"
  fi

  # 2. Shared code symlinks (shared.*, test_shared.*).
  "$ROOT/scripts/function-python-setup.sh" --function_name operations_api >/dev/null

  # 3. Isolated venv with the function's runtime deps (functions-framework, fastapi, ...).
  # The app requires Python >= 3.10. Honor $PYTHON, else prefer `python3` (matches the
  # other scripts), falling back to versioned interpreters; fail fast with a clear message.
  pick_python() {
    local c
    for c in "${PYTHON:-}" python3 python3.12 python3.11 python3.10; do
      [[ -z "$c" ]] && continue
      command -v "$c" >/dev/null 2>&1 || continue
      if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        echo "$c"; return 0
      fi
    done
    return 1
  }
  PY="$(pick_python)" || {
    echo "ERROR: Python >= 3.10 is required (your 'python3' is $(python3 -V 2>&1))." >&2
    echo "       Install Python 3.11+ or run with PYTHON=/path/to/python3.11 $0" >&2
    exit 1
  }

  VENV="$OPS_DIR/venv"
  # Rebuild the venv if it is missing or was built with an incompatible interpreter
  # (e.g. a stale pre-3.10 venv) so `pip install` never fails on Requires-Python.
  # Use the stdlib venv module (no install into the base interpreter -> avoids
  # triggering a pyenv rehash) rather than the `virtualenv` package.
  if [[ ! -x "$VENV/bin/python" ]] \
     || ! "$VENV/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    rm -rf "$VENV"
    "$PY" -m venv "$VENV"
  fi
  "$VENV/bin/python" -m pip install --disable-pip-version-check --quiet --upgrade pip
  "$VENV/bin/python" -m pip install --disable-pip-version-check --quiet -r "$OPS_DIR/requirements.txt"

  # 4. Test DB URLs (code reads FEEDS_DATABASE_URL / USERS_DATABASE_URL, not *_TEST).
  set -a; # shellcheck disable=SC1091
  source "$ROOT/config/.env.local"; set +a
  : "${FEEDS_DATABASE_URL_TEST:?FEEDS_DATABASE_URL_TEST not set in config/.env.local}"
  FEEDS_URL="$FEEDS_DATABASE_URL_TEST"
  USERS_URL="${USERS_DATABASE_URL_TEST:-${FEEDS_URL/MobilityDatabaseTest/MobilityDatabaseUsersTest}}"

  # 5. Bring up the test DB + apply migrations (schema only; no seed needed).
  if [[ "$USE_DOCKER" == 1 ]]; then
    need docker
    DC="docker compose"; $DC version >/dev/null 2>&1 || DC="docker-compose"
    echo "Bringing up test database + migrations..."
    $DC --env-file "$ROOT/config/.env.local" up -d postgres-test liquibase-test liquibase-user-test
  fi

  # 6. Start the real Cloud Function entrypoint (functions-framework -> main).
  #    LOCAL_ENV=True bypasses auth AND (see feeds_operations_impl) skips the
  #    best-effort external GCP side-effects that create/update would otherwise
  #    trigger (Pub/Sub dataset-download, Cloud Tasks revalidation, notifications),
  #    so those clients are never constructed and requests don't block on GCP.
  # Free the port in case a previous run left a server behind (functions-framework
  # forks a worker, so a stale listener would otherwise capture our requests).
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti "tcp:$PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
  fi
  echo "Starting Operations API on port $PORT ..."
  ( cd "$OPS_DIR/src" && \
    LOCAL_ENV=True \
    FEEDS_DATABASE_URL="$FEEDS_URL" \
    USERS_DATABASE_URL="$USERS_URL" \
    GOOGLE_CLIENT_ID="surface-test" \
    "$VENV/bin/functions-framework" --target main --source main.py --port "$PORT" \
    > /tmp/api-operations-surface-server.log 2>&1 ) &
  SERVER_PID=$!
  BASE_URL="http://localhost:$PORT"

  # 7. Wait until the DB is migrated AND the app answers (both needed for 200).
  echo -n "Waiting for API to be ready"
  ready=0
  for _ in $(seq 1 90); do
    if curl -fsS -o /dev/null "$BASE_URL/v1/operations/feeds?limit=1" 2>/dev/null; then ready=1; break; fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then echo " server exited early"; break; fi
    echo -n "."; sleep 1
  done
  echo
  if [[ "$ready" != 1 ]]; then
    echo "ERROR: API did not become ready. Server log:" >&2
    tail -n 40 /tmp/api-operations-surface-server.log >&2 || true
    exit 1
  fi
fi

cleanup() {
  if [[ "$KEEP_UP" == 1 ]]; then
    echo "Leaving server running (PID ${SERVER_PID:-n/a}) at $BASE_URL"
    return
  fi
  # Only tear down a server we started (not an external --url target).
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    # functions-framework forks a worker; kill anything still bound to our port
    # so no server survives the run.
    if command -v lsof >/dev/null 2>&1; then
      lsof -ti "tcp:$PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
    fi
  fi
}
trap cleanup EXIT INT TERM

# --- endpoint checks ----------------------------------------------------------
# check <method> <path> <allowed-status-csv> [json-body]
PASS=0; FAIL=0; FAILURES=()
BODY_FILE="$(mktemp)"

check() {
  local method="$1" path="$2" allowed="$3" body="${4:-}"
  # --max-time guarantees a hung endpoint fails fast (code 000) instead of
  # stalling the whole run; a smoke test must never block.
  local args=(-s -o "$BODY_FILE" -w '%{http_code}' --connect-timeout 5 --max-time 30 \
    -X "$method" "$BASE_URL$path")
  [[ -n "$body" ]] && args+=(-H 'Content-Type: application/json' --data "$body")
  local code; code="$(curl "${args[@]}" 2>/dev/null || true)"; code="${code:-000}"
  if [[ ",$allowed," == *",$code,"* ]]; then
    printf '  PASS  %-6s %-46s -> %s\n' "$method" "$path" "$code"
    PASS=$((PASS + 1))
  else
    printf '  FAIL  %-6s %-46s -> %s (expected one of: %s)\n' "$method" "$path" "$code" "$allowed"
    printf '        body: %s\n' "$(head -c 200 "$BODY_FILE")"
    FAIL=$((FAIL + 1)); FAILURES+=("$method $path -> $code")
  fi
}

# We hit the read/list endpoints and the feed create->get->update lifecycle
# (feeds have a real create endpoint, so we reuse the *returned* id -- never a
# fabricated or non-existent id, and we never create/mutate feature flags or probe
# made-up users). The by-id / mutation endpoints that would need a fabricated id
# are covered structurally, without HTTP, by tests/test_routes_are_sync.py.
STAMP="$(date +%s)"
echo "Hitting Operations API endpoints at $BASE_URL"

# --- Feeds --------------------------------------------------------------------
check GET  "/v1/operations/feeds?limit=1" 200

check POST "/v1/operations/feeds/gtfs" 200,201 \
  "{\"provider\":\"api_surface\",\"operational_status\":\"wip\",\"source_info\":{\"producer_url\":\"https://example.com/api-surface-gtfs-$STAMP.zip\"}}"
GTFS_ID="$(jq -r '.stable_id // .id // empty' "$BODY_FILE" 2>/dev/null || true)"; GTFS_ID="${GTFS_ID:-surface-missing}"

check POST "/v1/operations/feeds/gtfs_rt" 200,201 \
  "{\"provider\":\"api_surface\",\"operational_status\":\"wip\",\"entity_types\":[\"vp\"],\"source_info\":{\"producer_url\":\"https://example.com/api-surface-gtfsrt-$STAMP\"}}"
RT_ID="$(jq -r '.stable_id // .id // empty' "$BODY_FILE" 2>/dev/null || true)"; RT_ID="${RT_ID:-surface-missing}"

check GET  "/v1/operations/gtfs_feeds/$GTFS_ID" 200,404
check GET  "/v1/operations/gtfs_feeds/$GTFS_ID/availability" 200,404
check GET  "/v1/operations/gtfs_rt_feeds/$RT_ID" 200,404
check PUT  "/v1/operations/feeds/gtfs" 200,204,400 \
  "{\"id\":\"$GTFS_ID\",\"status\":\"active\",\"operational_status_action\":\"no_change\"}"
check PUT  "/v1/operations/feeds/gtfs_rt" 200,204,400 \
  "{\"id\":\"$RT_ID\",\"status\":\"active\",\"entity_types\":[\"vp\"],\"operational_status_action\":\"no_change\"}"

# --- Licenses -----------------------------------------------------------------
check GET  "/v1/operations/licenses?limit=1" 200
check POST "/v1/operations/licenses:match" 200 \
  "{\"license_url\":\"https://creativecommons.org/licenses/by/4.0/\"}"
check POST "/v1/operations/licenses:propagate_match" 200,400 \
  "{\"license_id\":\"CC-BY-4.0\",\"license_url\":\"https://creativecommons.org/licenses/by/4.0/\",\"dry_run\":true}"

# --- Feature flags (list only; a smoke run must not create/mutate config flags)
check GET  "/v1/operations/feature-flags" 200

# --- Users (list only; there is no create-user endpoint, so no real id to test
#     the by-id endpoints against -- covered by the static route guard instead)
check GET  "/v1/operations/users?limit=1" 200

# --- summary ------------------------------------------------------------------
rm -f "$BODY_FILE"
echo
echo "api_surface: $PASS passed, $FAIL failed."
if [[ "$FAIL" -gt 0 ]]; then
  printf 'Failed endpoints:\n'; printf '  - %s\n' "${FAILURES[@]}"
  exit 1
fi
echo "All exercised endpoints returned an expected, non-5xx response."
