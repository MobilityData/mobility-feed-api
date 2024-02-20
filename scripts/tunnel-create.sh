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

#
# This script creates a SSH tunnel between the local machine and a GCP database using a SSH on a GCP instance.
# Usage:
#  ./scripts/tunnel-create.sh -project_id mobility-feeds-qa -zone northamerica-northeast1-a -instance vm-name -target_account user -db_instance dn-instance-name
# Parameters:
# -project_id <PROJECT_ID>          The GCP project id
# -zone <ZONE>                      The GCP zone network.
# -instance <INSTANCE>              Name of the instance deployed within the GCP zone.
# -port <PORT>                      Local port to map. Default 8888.
# -target_port <TARGET_PORT>        Remote port of the target machine. Default 5432.
# -target_account <TARGET_ACCOUNT>  Account in the target machine.
# -db_instance <DB_INSTANCE>        Name of the deployed DB instance.
#

PROJECT_ID=""
ZONE=""
INSTANCE=""
PORT="8888"
TARGET_PORT="5432"
TARGET_ACCOUNT=""
DB_INSTANCE=""

display_usage() {
    printf "\nThis script creates a SSH tunnel between the local machine and a GCP database using a SSH on a GCP instance."
    printf "\nScript Usage:\n"
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -project_id <PROJECT_ID>            The GCP project id."
    echo "  -zone <ZONE>                        The GCP zone network."
    echo "  -instance <INSTANCE>                Name of the instance deployed within the GCP zone."
    echo "  -port <PORT>                        Optional - local port to map. Default 8888."
    echo "  -target_port <TARGET_PORT>          Optional - remote port of the target machine. Default 5432."
    echo "  -target_account <TARGET_ACCOUNT>    Account in the target machine."
    echo "  -db_instance <DB_INSTANCE>          Name of the DB instance deployed in GCP."
    exit 1
}

while [[ $# -gt 0 ]]; do
    key="$1"

    case $key in
    -project_id)
        PROJECT_ID="$2"
        shift # past argument
        shift # past value
        ;;
    -zone)
        ZONE="$2"
        shift # past argument
        shift # past value
        ;;
    -instance)
        INSTANCE="$2"
        shift # past argument
        shift # past value
        ;;
    -target_account)
        TARGET_ACCOUNT="$2"
        shift # past argument
        shift # past value
        ;;
    -db_instance)
        DB_INSTANCE="$2"
        shift # past argument
        shift # past value
        ;;
    -h | --help)
        display_usage
        ;;
    *)        # unknown option
        shift # past argument
        ;;
    esac
done

# Check if required parameters are provided
if [[ -z "${PROJECT_ID}" || -z "${ZONE}" || -z "${INSTANCE}" || -z "${TARGET_ACCOUNT}" || -z "${DB_INSTANCE}" ]]; then
    echo "Missing required parameters."
    display_usage
fi

# Making sure the machine is up
gcloud compute instances start ${INSTANCE} --zone=${ZONE} --project=${PROJECT_ID} >/dev/null

# Get the public IPs associated with the instance.
ips=$(gcloud compute instances describe ${INSTANCE} --zone=${ZONE} --project=${PROJECT_ID} --format='get(networkInterfaces.accessConfigs.natIP)')

# Get the DB internal IP address
target_ip=$(gcloud sql instances describe ${DB_INSTANCE} --project=${PROJECT_ID} --format='get(ipAddresses[0].ipAddress)')


# Getting the first IP
ip=$(echo $ips | sed "s/\['\([^']*\)'.*/\1/")

# Creating SSH tunnel
ssh -fN -L ${PORT}:${target_ip}:${TARGET_PORT} ${TARGET_ACCOUNT}@${ip}
