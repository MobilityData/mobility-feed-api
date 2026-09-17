#!/bin/bash
#
#
#  MobilityData 2026
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
#

# Converts a GTFS feed to Parquet on this machine, so the viewer can be worked on
# without a bucket, a database, a task queue or any GCP credentials. The conversion is
# the parquet_builder function's own, imported rather than copied, so the output is
# what a real build would produce.
#
# Only duckdb is needed; it is installed into a throwaway virtualenv on first run.
#
# Usage:
#   parquet-generate-local.sh <feed-id | dataset-id | feed.zip | folder/> [options]
#
# Options are passed straight through; run with --help for the full list.
#
# Examples:
#   parquet-generate-local.sh mdb-1210
#   parquet-generate-local.sh mdb-1210-202402121801 --env dev
#   parquet-generate-local.sh ./gtfs.zip --out ../ops-web/public/datasets/mdb-1210
#   parquet-generate-local.sh mdb-1210 --serve

set -euo pipefail

SCRIPT_PATH="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
FUNCTION_PATH="$SCRIPT_PATH/../functions-python/parquet_builder"
VENV="$FUNCTION_PATH/venv"

if [ $# -eq 0 ]; then
  echo "Usage: parquet-generate-local.sh <feed-id | dataset-id | feed.zip | folder/> [--out DIR] [--serve [PORT]]" >&2
  echo "Run with --help for all options." >&2
  exit 1
fi

# The function's own venv when it exists (tests create it), otherwise a minimal one.
# Only duckdb is imported by this path - none of the cloud dependencies are touched.
if [ ! -x "$VENV/bin/python" ]; then
  echo "INFO: creating virtualenv for parquet_builder"
  python3 -m venv "$VENV"
fi

if ! "$VENV/bin/python" -c "import duckdb" >/dev/null 2>&1; then
  echo "INFO: installing duckdb"
  "$VENV/bin/python" -m pip install --disable-pip-version-check -q duckdb
fi

PYTHONPATH="$FUNCTION_PATH/src" exec "$VENV/bin/python" \
  "$FUNCTION_PATH/src/scripts/generate_local.py" "$@"
