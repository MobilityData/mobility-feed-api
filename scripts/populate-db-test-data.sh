#!/bin/bash

#
#
#  MobilityData 2024
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