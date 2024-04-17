#!/bin/bash

#
# This script populates the local instance of the database with test data.
# As a requirement, you need to have the local instance of the database running on the port defined in config/.env.local
# The default path to the test data is api/tests/test_data/test_datasets.json
# Usage:
#   populate-db-test-data.sh <path to sources.csv>
#

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

# default value
filepath=tests/test_data/test_datasets.json
# if $1 parameter is set, then use it
if [ ! -z "$1" ]; then
  filepath="$1"
fi 
(cd $SCRIPT_PATH/../api/ && pip3 install -r requirements.txt && PYTHONPATH=src python src/scripts/populate_db_test_data.py --filepath "$filepath")