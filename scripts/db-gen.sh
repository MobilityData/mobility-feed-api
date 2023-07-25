#!/bin/bash

#
# This script generates the sqlalchemy models using sqlacodegen.
# As a requirement, you need to have the local instance of the database running on the port defined in config/.env.local
# Usage:
#   db-gen.sh
#

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

# generate sql alchemy models
OUT_FILE=$SCRIPT_PATH/../api/src/database_gen/sqlacodegen_models.py
ENV_PATH=$SCRIPT_PATH/../config/.env.local
source "$ENV_PATH"
rm -rf "$SCRIPT_PATH/../api/src/database_gen/"
mkdir "$SCRIPT_PATH/../api/src/database_gen/"
pip3 install -r "${SCRIPT_PATH}/../api/requirements.txt"
sqlacodegen "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}" --outfile "${OUT_FILE}"

rm -rf "$TEMP_FILE"

