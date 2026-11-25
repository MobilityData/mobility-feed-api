#!/bin/bash
#
# Seeds the local database for the PR integration tests, so the tests compare the API against the
# same data the database was built from. Everything comes from committed files, nothing is fetched:
#   - GTFS and GTFS-RT feeds: the given sources.csv, the same file the tests read
#     (integration-tests/fixtures/sources.csv by default).
#   - GBFS feeds and versions: integration-tests/fixtures/gbfs_systems.csv and gbfs_versions.json.
#   - Every other entity the endpoints read (licenses and rules, datasets, validation reports,
#     availability checks, the Seal of Reliability, geopolygons, users and their feature flags):
#     integration-tests/fixtures/test_data.json.
#
# Requires the database to be migrated (Liquibase) and the SQLAlchemy models generated (db-gen.sh).
# Nothing is published to Pub/Sub: ENVIRONMENT is forced to "local".
#
# Usage: scripts/integration-tests-seed-db.sh <path to sources.csv>

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <path to sources.csv>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCES_CSV="$(realpath "$1")"
FIXTURES_DIR="${REPO_ROOT}/integration-tests/fixtures"

export ENVIRONMENT=local

echo "INFO: Installing API requirements"
pip3 install --disable-pip-version-check -q -r "${REPO_ROOT}/api/requirements.txt"

cd "${REPO_ROOT}/api"
export PYTHONPATH=src

echo "INFO: Populating GTFS and GTFS-RT feeds from ${SOURCES_CSV}"
python src/scripts/populate_db_gtfs.py --filepath "${SOURCES_CSV}"

echo "INFO: Populating GBFS feeds from fixtures"
python - --filepath "${FIXTURES_DIR}/gbfs_systems.csv" <<'PYCODE'
from scripts.populate_db import set_up_configs
from scripts.populate_db_gbfs import GBFSDatabasePopulateHelper

GBFSDatabasePopulateHelper(set_up_configs()).initialize(
    trigger_downstream_tasks=False, fetch_url=False
)
PYCODE

echo "INFO: Populating GBFS versions from fixtures"
python src/scripts/populate_db_test_data.py --filepath "${FIXTURES_DIR}/gbfs_versions.json"

echo "INFO: Populating licenses, datasets, reports and the other entities from fixtures"
python src/scripts/populate_db_test_data.py --filepath "${FIXTURES_DIR}/test_data.json"

echo "SUCCESS: Integration tests database seeded."
