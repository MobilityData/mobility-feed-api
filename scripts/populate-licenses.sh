#!/usr/bin/env bash
set -euo pipefail

# Populate local database with license rules and licenses using the tasks_executor function code.
# This script will:
#  1. Run the license rules population task (creates/updates rules)
#  2. Run the licenses population task (links licenses to rules)
# Both steps can be executed in dry-run mode with --dry-run to verify actions.
#
# Usage:
#   ./scripts/populate-licenses.sh            # real execution
#   ./scripts/populate-licenses.sh --dry-run  # simulate without DB writes
#
# Requirements:
#  - Local database running (docker compose up ...)
#  - FEEDS_DATABASE_URL exported in environment or present in functions-python/tasks_executor/.env.local
#  - Network access to GitHub (public repo MobilityData/licenses-aas)

SCRIPT_DIR="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FX_NAME="tasks_executor"
FX_PATH="${REPO_ROOT}/functions-python/${FX_NAME}"
FX_SRC_PATH="${FX_PATH}/src"

DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# //' | sed '1,2d'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -d "$FX_SRC_PATH" ]]; then
  echo "ERROR: tasks_executor source not found at $FX_SRC_PATH" >&2
  exit 1
fi

# Ensure virtualenv (reuse function runner conventions)
if [[ ! -d "$FX_PATH/venv" ]]; then
  echo "INFO: provisioning virtual environment (first run)"
  pushd "$FX_PATH" >/dev/null
  pip3 install --disable-pip-version-check virtualenv >/dev/null
  python3 -m virtualenv venv >/dev/null
  venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt >/dev/null
  popd >/dev/null
fi

# Load local env vars if present (e.g., FEEDS_DATABASE_URL)
if [[ -f "$FX_PATH/.env.local" ]]; then
  echo "INFO: Loading env vars from $FX_PATH/.env.local"
  set -o allexport
  # shellcheck disable=SC1090
  source "$FX_PATH/.env.local"
  set +o allexport
fi

# Also load repository-level config/.env.local for DB settings (preferred)
if [[ -f "$REPO_ROOT/config/.env.local" ]]; then
  echo "INFO: Loading env vars from $REPO_ROOT/config/.env.local"
  set -o allexport
  # shellcheck disable=SC1090
  source "$REPO_ROOT/config/.env.local"
  set +o allexport
fi

# If FEEDS_DATABASE_URL is still not set, attempt to construct it from POSTGRES_* vars
if [[ -z "${FEEDS_DATABASE_URL:-}" ]]; then
  if [[ -n "${POSTGRES_USER:-}" && -n "${POSTGRES_PASSWORD:-}" && -n "${POSTGRES_DB:-}" ]]; then
    DB_HOST="${POSTGRES_HOST:-localhost}"
    DB_PORT="${POSTGRES_PORT:-5432}"
    FEEDS_DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${DB_HOST}:${DB_PORT}/${POSTGRES_DB}"
    export FEEDS_DATABASE_URL
    echo "INFO: Constructed FEEDS_DATABASE_URL from POSTGRES_* variables."
  else
    echo "WARNING: FEEDS_DATABASE_URL is not set and POSTGRES_* vars are incomplete. The script will likely fail to connect to DB." >&2
  fi
fi

# Log target DB (mask password)
if [[ -n "${FEEDS_DATABASE_URL:-}" ]]; then
  MASKED_URL="${FEEDS_DATABASE_URL/:${POSTGRES_PASSWORD:-***}/:***}"
  echo "INFO: Using FEEDS_DATABASE_URL=${MASKED_URL}"
fi

PYTHON_BIN="$FX_PATH/venv/bin/python"
export PYTHONPATH="$FX_SRC_PATH"

# Convert shell boolean to Python boolean literal
if [[ "$DRY_RUN" == "true" ]]; then PY_DRY=True; else PY_DRY=False; fi

echo "INFO: Running populate_license_rules (dry_run=${DRY_RUN})"
"$PYTHON_BIN" - <<PYCODE
from tasks.licenses.populate_license_rules import populate_license_rules_task
populate_license_rules_task(dry_run=${PY_DRY})
PYCODE

echo "INFO: Running populate_licenses (dry_run=${DRY_RUN})"
"$PYTHON_BIN" - <<PYCODE
from tasks.licenses.populate_licenses import populate_licenses_task
populate_licenses_task(dry_run=${PY_DRY})
PYCODE

echo "SUCCESS: License rules and licenses population completed (dry_run=${DRY_RUN})."