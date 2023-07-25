#!/bin/bash

#
# This script populates the local instance of the database.
# As a requirement, you need to have the local instance of the database running on the port defined in config/.env.local
# The csv file containing the data has to be in the same format as https://bit.ly/catalogs-csv
# Usage:
#   populate-db.sh <path to sources.csv>
#   populate-db.sh "/Users/chaimaa/Downloads/[Public] Catalogs - July 20  - sources (79).csv"
#

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

(cd $SCRIPT_PATH/../api/ && pip3 install -r requirements.txt && PYTHONPATH=src python src/scripts/populate_db.py --filepath "$1")