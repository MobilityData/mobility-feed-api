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
# This script delete the data and the local database container.
# Then it downloads the latest csv file and populates the database applying the liquibase changes.
# Usage:
#       ./docker-localdb-rebuild-data.sh --populate-db
# Options:
#       --populate-db: populate the database with the latest csv file
# Dependencies:
#      docker, docker-compose, wget

target_csv_file="catalogs.csv"
# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

display_usage() {
  printf "\nThis script deletes the data and the local database container.\n"
  printf "\nScript Usage:\n"
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  --populate-db <TEST_FILE> Populate the database with the latest csv file."
  echo "  --populate-test-data      Populate the database with the test data."
  echo "  --use-test-db             Populate the test database."
  echo "  --help                    Display help content."
  exit 1
}

POPULATE_DB=false
POPULATE_TEST_DATA=false
USE_TEST_DB=false
while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
  --help)
    display_usage
    ;;
  --populate-db)
    POPULATE_DB=true
    shift # past argument
    ;;
  --populate-test-data)
    POPULATE_TEST_DATA=true
    shift # past argument
    ;;
  --use-test-db)
    export USE_TEST_DB=true
    shift # past argument
    ;;
  *)      # unknown option
    shift # past argument
    ;;
  esac
done

container_name="database"
docker_service="liquibase"
data_dir="$SCRIPT_PATH/../data"

if [ "$USE_TEST_DB" = true ]; then
    container_name="database_test"
    docker_service="liquibase-test"
    data_dir="$SCRIPT_PATH/../data-test"
fi

# Stop and remove the container
docker stop $container_name
docker rm $container_name

# delete the data
rm -rf $data_dir

# Add a slight delay because sometimes Docker does not seem ready after the rm.
sleep 5

# Start the container and run the liquibase
docker compose --env-file $SCRIPT_PATH/../config/.env.local -f $SCRIPT_PATH/../docker-compose.yaml up -d $docker_service
# wait for the liquibase to finish
sleep 20

# generate the models
$SCRIPT_PATH/db-gen.sh


if [ "$POPULATE_DB" = true ]; then
    # download the latest csv file and populate the db
    mkdir $SCRIPT_PATH/../data/
    wget -O $SCRIPT_PATH/../data/$target_csv_file https://share.mobilitydata.org/catalogs-csv
    # populate db
    full_path="$(readlink -f $SCRIPT_PATH/../data/$target_csv_file)"
    $SCRIPT_PATH/populate-db.sh $full_path
    printf "\n---------\nCompleted: populating catalog data.\n---------\n"
    $SCRIPT_PATH/populate-licenses.sh
fi

if [ "$POPULATE_TEST_DATA" = true ]; then
    # populate test data
    $SCRIPT_PATH/populate-db-test-data.sh
    printf "\n---------\nCompleted: populating test data.\n---------\n"
fi

printf "\n---------\nSuccess: Rebuilding the database.\n---------\n"
