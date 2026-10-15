#!/bin/bash

#
# Generates SQLAlchemy models for the users database (issue #1683)
# using sqlacodegen. Mirrors scripts/db-gen.sh but targets POSTGRES_USER_DB.
#
# Requires the local users DB to be running and migrated (see
# scripts/docker-localdb-rebuild-data.sh and liquibase/changelog_user.xml).
#
# Usage:
#   db-gen-user.sh [output path from root]
#

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

# Default filename for OUT_FILE
DEFAULT_FILENAME="api/src/shared/users_database_gen/sqlacodegen_models.py"
# Use the first argument as the filename for OUT_FILE; if not provided, use the default filename
FILENAME=${1:-$DEFAULT_FILENAME}
OUT_FILE=$SCRIPT_PATH/../$FILENAME

ENV_PATH=$SCRIPT_PATH/../config/.env.local
source "$ENV_PATH"

rm -rf "$SCRIPT_PATH/../api/src/shared/users_database_gen/"
mkdir "$SCRIPT_PATH/../api/src/shared/users_database_gen/"
pip3 install -r "${SCRIPT_PATH}/../api/requirements.txt" > /dev/null

# removing sqlacodegen-user.log file
if [ -s ${SCRIPT_PATH}/sqlacodegen-user.log ]
then
  rm ${SCRIPT_PATH}/sqlacodegen-user.log
fi

PORT=$POSTGRES_PORT
# The users DB lives on the same instance as the catalog DB in both local
# (host postgres / postgres-test container) and prod (same Cloud SQL instance).
DB=${POSTGRES_USER_DB:-MobilityDatabaseUsers}
if [ "$USE_TEST_DB" = true ]; then
    PORT=$POSTGRES_TEST_PORT
    DB=${POSTGRES_USER_TEST_DB:-MobilityDatabaseUsersTest}
fi

echo "Generating SQLAlchemy models for users DB ($DB) using sqlacodegen..."
sqlacodegen "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${PORT}/${DB}?options=-csearch_path%3Dpublic" --outfile "${OUT_FILE}" --options use_inflect &> ${SCRIPT_PATH}/sqlacodegen-user.log
sqlacodegen_error=($?)
echo "Completed SQLAlchemy models generation for users DB"

printf "/n--- Generated users models ---/n"
cat ${OUT_FILE}
echo "/n---End of generated users models ---/n"

print_logs (){
  if [ -s ${SCRIPT_PATH}/sqlacodegen-user.log ]
  then
    echo "sqlacodegen-user.log"
    echo "--------------------"
    cat ${SCRIPT_PATH}/sqlacodegen-user.log
    echo "--------------------"
  fi
}

if [ $sqlacodegen_error -eq 0 ]
then
  printf "\nSuccess: executing sqlacodegen for users DB.\n\n"
  print_logs
  exit 0
else
  printf "\nFailure executing sqlacodegen for users DB\n\n"
  print_logs
  printf "\n"
  exit 1
fi
