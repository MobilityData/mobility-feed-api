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
# This script builds the Feeds API container and push it to a GCP Artifactory registry.
# The resulting image can be pull as: docker pull <region>-docker.pkg.dev/<project_id>/<repo_name>/<service>:<version>
# Parameters:
# -project_id <PROJECT_ID>      The GCP project id
# -region <REGION>              The GCP region.
# -repo_name <REPOSITORY_NAME>  The GCP Artifactory repository name.
# -service <SERVICE>            The cloud run service name.
# -version <VERSION>            The container's image version to push
#

display_usage() {
  printf "\nThis script builds the Feeds API container and push it to a GCP Artifactory registry."
  printf "\nThe resulting image can be pull as: docker pull <region>-docker.pkg.dev/<project_id>/<repo_name>/<service>:<version>"
  printf "\nScript Usage:\n"
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  -project_id <PROJECT_ID>      The GCP project id."
  echo "  -region <REGION>              The GCP region."
  echo "  -repo_name <REPOSITORY_NAME>  The GCP Artifactory repository name."
  echo "  -service <SERVICE>            The cloud run service name."
  echo "  -version <VERSION>            The container's image version to push."
  echo "  -dockerfile <DOCKERFILE>      Path to the Dockerfile (default: api/Dockerfile)."
  echo "  -context <CONTEXT>            Docker build context directory (default: api/)."
  exit 1
}

PROJECT_ID=""
SERVICE=""
REGION=""
VERSION=""
DOCKERFILE=""
CONTEXT=""

while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
    -project_id)
      PROJECT_ID="$2"
      shift # past argument
      shift # past value
      ;;
    -service)
      SERVICE="$2"
      shift # past argument
      shift # past value
      ;;
    -repo_name)
      REPO_NAME="$2"
      shift # past argument
      shift # past value
      ;;
    -region)
      REGION="$2"
      shift # past argument
      shift # past value
      ;;
    -version)
      VERSION="$2"
      shift # past argument
      shift # past value
      ;;
    -dockerfile)
      DOCKERFILE="$2"
      shift # past argument
      shift # past value
      ;;
    -context)
      CONTEXT="$2"
      shift # past argument
      shift # past value
      ;;
    -h|--help)
      display_usage
      ;;
    *) # unknown option
      shift # past argument
      ;;
  esac
done

# Check if required parameters are provided
if [[ -z "${PROJECT_ID}" || -z "${SERVICE}" || -z "${REGION}" || -z "${VERSION}" ]]; then
  echo "Missing required parameters."
  display_usage
fi

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

# Default build context is api/, default Dockerfile is inside the context
BUILD_CONTEXT="${CONTEXT:-$SCRIPT_PATH/../api}"
DOCKERFILE_ARG=""
if [[ -n "${DOCKERFILE}" ]]; then
  DOCKERFILE_ARG="-f ${DOCKERFILE}"
fi

DOCKER_TAG=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE}:${VERSION}

# Build your Docker image
docker buildx build --push --platform linux/amd64 --no-cache $DOCKERFILE_ARG -t $DOCKER_TAG $BUILD_CONTEXT
