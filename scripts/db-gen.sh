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
COPY_TO_PATH=$SCRIPT_PATH/../functions-python/database_gen/

ENV_PATH=$SCRIPT_PATH/../config/.env.local
source "$ENV_PATH"
rm -rf "$SCRIPT_PATH/../api/src/database_gen/"
mkdir "$SCRIPT_PATH/../api/src/database_gen/"
pip3 install -r "${SCRIPT_PATH}/../api/requirements.txt" > /dev/null

# removing sqlacodegen.log file
if [ -s ${SCRIPT_PATH}/sqlacodegen.log ]
then
  rm ${SCRIPT_PATH}/sqlacodegen.log
fi

echo "Generating SQLAlchemy models using sqlacodegen..."
# Running sqlacodegen and capturing errors and warnings in the sqlacodegen.log file
sqlacodegen "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}?options=-csearch_path%3Dpublic" --outfile "${OUT_FILE}" --options use_inflect,nobidi &> ${SCRIPT_PATH}/sqlacodegen.log
sqlacodegen_error=($?)
echo "Completed SQLAlchemy models generation"

printf "/n--- Generated models ---/n"
cat ${OUT_FILE}
echo "/n---End of generated models ---/n"

rm -rf "${COPY_TO_PATH}"
mkdir -p "${COPY_TO_PATH}"
cp "${OUT_FILE}" "${COPY_TO_PATH}"

print_logs (){
  if [ -s ${SCRIPT_PATH}/sqlacodegen.log ]
  then
    echo "sqlacodegen.log"
    echo "----------------"
    cat ${SCRIPT_PATH}/sqlacodegen.log
    echo "----------------"
  fi
}

# Check the exit status of sqlacodegen
if [ $sqlacodegen_error -eq 0 ]
then
  printf "\nSuccess: executing sqlacodegen.\n\n"
  print_logs
  exit 0
else
  printf "\nFailure executing sqlacodegen\n\n"
  print_logs
  printf "\n"
  exit 1
fi


