#!/bin/bash

#
# This script generates the SQLAlchemy models using sqlacodegen.
# As a requirement, you need to have the local instance of the database running on the port defined in config/.env.local
# Usage:
#   db-gen.sh [output path from root]
#

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

# Default filename for OUT_FILE
DEFAULT_FILENAME="api/src/database_gen/sqlacodegen_models.py"
# Use the first argument as the filename for OUT_FILE; if not provided, use the default filename
FILENAME=${1:-$DEFAULT_FILENAME}
OUT_FILE=$SCRIPT_PATH/../$FILENAME

ENV_PATH=$SCRIPT_PATH/../config/.env.local
source "$ENV_PATH"
rm -rf "$SCRIPT_PATH/../api/src/database_gen/"
mkdir "$SCRIPT_PATH/../api/src/database_gen/"
pip3 install -r "${SCRIPT_PATH}/../api/requirements.txt"

# removing sqlacodegen.log file
if [ -s ${SCRIPT_PATH}/sqlacodegen.log ]
then
  rm ${SCRIPT_PATH}/sqlacodegen.log
fi

# Running sqlacodegen and capturing errors and warnings in the sqlacodegen.log file
sqlacodegen "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}" --outfile "${OUT_FILE}" &> ${SCRIPT_PATH}/sqlacodegen.log

# Check the exit status of sqlacodegen and the log file for any output
if [ $? -eq 0 ] && [ ! -s ${SCRIPT_PATH}/sqlacodegen.log ]
then
  echo "Success: executing sqlacodegen."
  exit 0
else
  echo "Failure executing sqlacodegen" >&2
  printf "\nsqlacodegen error:\n"
  cat ${SCRIPT_PATH}/sqlacodegen.log
  printf "\n"
  exit 1
fi
