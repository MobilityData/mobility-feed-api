#!/bin/bash

#
#
#  MobilityData 2023
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
#

# This script delete the data and the local database container.
# Then it downloads the latest csv file and populates the database applying the liquibase changes.
# Usage:
#       ./docker-localdb-rebuild-data.sh

container_name="database"
target_csv_file="catalogs.csv"
# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

# Stop and remove the container
docker stop $container_name
docker rm $container_name

# delete the data
rm -rf $SCRIPT_PATH/../data

# Start the container and run the liquibase
docker-compose -f $SCRIPT_PATH/../docker-compose.yaml up -d liquibase
# wait for the liquibase to finish
sleep 20

# generate the models
$SCRIPT_PATH/db-gen.sh

# populate the db if --populate-db is set
if [ "$1" == "--populate-db" ]; then
    download the latest csv file and populate the db
    mkdir $SCRIPT_PATH/../data/
    wget -O $SCRIPT_PATH/../data/$target_csv_file https://bit.ly/catalogs-csv
    # populate db
    full_path="$(readlink -f $SCRIPT_PATH/../data/$target_csv_file)"
    $SCRIPT_PATH/populate-db.sh $full_path
fi

