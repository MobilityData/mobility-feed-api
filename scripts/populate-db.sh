#!/bin/bash

#
# This script populates the local instance of the database.
# As a requirement, you need to have the local instance of the database running on the port defined in config/.env.local
# The csv file containing the data has to be in the same format as https://storage.googleapis.com/storage/v1/b/mdb-csv/o/sources.csv?alt=media
# Usage:
#   populate-db.sh <path to sources.csv> [data_type]
#

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

# Set the data_type, defaulting to 'gtfs'
DATA_TYPE=${2:-gtfs}

# Determine the script to run based on the data_type
if [ "$DATA_TYPE" = "gbfs" ]; then
    SCRIPT_NAME="populate_db_gbfs.py"
else
    SCRIPT_NAME="populate_db_gtfs.py"
fi

# Run the appropriate script
(cd "$SCRIPT_PATH"/../api/ && pip3 install -r requirements.txt && PYTHONPATH=src python src/scripts/$SCRIPT_NAME --filepath "$1")
