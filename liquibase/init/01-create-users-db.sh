#!/bin/bash
# Creates the local "users" database alongside the catalog DB on first start
# of the postgres container. The postgres image only runs scripts in
# /docker-entrypoint-initdb.d/ when the data directory is empty, which matches
# how scripts/docker-localdb-rebuild-data.sh wipes ./data before bringing the
# container back up.
#
# The DB name comes from POSTGRES_USER_DB (config/.env.local). Falls back to
# "MobilityDatabaseUsers" if unset.

set -e

USER_DB_NAME="${POSTGRES_USER_DB:-MobilityDatabaseUsers}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE "${USER_DB_NAME}";
EOSQL
