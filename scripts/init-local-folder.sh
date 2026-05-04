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

# This script initializes a local development environment for a new branch/folder.
# It rebuilds the local and test databases, regenerates SQLAlchemy models,
# FastAPI stubs, and Operations API schema and stubs.
#
# Usage:
#   ./init-local-folder.sh [--populate-db]
#
# Options:
#   --populate-db  Download the latest CSV from GCS and populate the main database.
#                  Without this flag, the database is only rebuilt with Liquibase migrations.
#
# Dependencies:
#   docker, docker-compose, wget, openapi-generator (setup-openapi-generator.sh), yq (v4+)

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

POPULATE_DB=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --populate-db) POPULATE_DB=true; shift ;;
    --help)
      echo "Usage: $0 [--populate-db]"
      echo "  --populate-db  Download and populate the main DB with the latest CSV data."
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

echo "==> Rebuilding main local database..."
if [ "$POPULATE_DB" = true ]; then
  "$SCRIPT_PATH/docker-localdb-rebuild-data.sh" --populate-db
else
  "$SCRIPT_PATH/docker-localdb-rebuild-data.sh"
fi

echo "==> Rebuilding test database..."
"$SCRIPT_PATH/docker-localdb-rebuild-data.sh" --use-test-db

echo "==> Generating SQLAlchemy models (db-gen)..."
"$SCRIPT_PATH/db-gen.sh"

echo "==> Generating FastAPI stubs (api-gen)..."
"$SCRIPT_PATH/api-gen.sh"

echo "==> Setting up the OpenApi Generator"
"$SCRIPT_PATH/setup-openapi-generator.sh"

echo "==> Syncing Operations API schema..."
"$SCRIPT_PATH/api-operations-update-schema.sh"

echo "==> Generating Operations API stubs (api-operations-gen)..."
"$SCRIPT_PATH/api-operations-gen.sh"

echo "==> Setting up all Python functions..."
"$SCRIPT_PATH/function-python-setup.sh" --all

echo "==> Local folder initialization complete."

