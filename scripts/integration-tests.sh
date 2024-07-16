#!/bin/bash

# This script is used to run the integration tests.
# Usage:
#   integration-tests.sh -u <API URL> -f <FILE PATH> [-c <CLASS NAMES>]
#
# Options:
#   -u  URL of the API to test against
#   -f  File path for the data file to be used in tests
#   -c  Optional, comma-separated list of test class names to include

function print_help() {
  echo "Usage: $0 -u <API URL> -f <FILE PATH> [-c <CLASS NAMES>]"
  echo ""
  echo "Options:"
  echo "  -u  URL of the API to test against"
  echo "  -f  File path for the data file to be used in tests"
  echo "  -c  Optional, comma-separated list of test class names to include"
  exit 1
}

# Initialize include_classes as an empty string
INCLUDE_CLASSES=""

while getopts ":u:f:c:h" opt; do
  case ${opt} in
    u ) URL=$OPTARG ;;
    f ) FILE_PATH=$OPTARG ;;
    c ) INCLUDE_CLASSES=$OPTARG ;;
    h ) print_help ;;
    \? ) print_help ;;
  esac
done

if [ -z "${URL}" ]; then
    echo "Error: API URL (-u) not provided."
    print_help
fi

if [ -z "${FILE_PATH}" ]; then
    echo "Error: File path (-f) not provided."
    print_help
fi

# Check if DUMMY_TOKEN is set as an environment variable and use it if provided
if [ -n "${DUMMY_TOKEN}" ]; then
    ACCESS_TOKEN=${DUMMY_TOKEN}
else
    # Check if REFRESH_TOKEN is set as an environment variable
    if [ -z "${REFRESH_TOKEN}" ]; then
        echo "Error: REFRESH_TOKEN environment variable is not set."
        echo "Please ensure the REFRESH_TOKEN is set as an environment variable."
        exit 1
    fi

    # Get the access token
    ACCESS_TOKEN=$(curl -X POST -H "Content-Type: application/json" -d "{\"refresh_token\": \"${REFRESH_TOKEN}\"}" "${URL}/v1/tokens" | jq -r '.access_token')
    if [ -z "${ACCESS_TOKEN}" ] || [ "${ACCESS_TOKEN}" == "null" ]; then
        echo "Failed to obtain access token."
        exit 1
    fi
fi

export ACCESS_TOKEN

# Check if DATASETS_LIMIT is set as an environment variable and use it if provided
if [ -n "${DATASETS_LIMIT}" ]; then
    export DATASETS_LIMIT
fi

SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
PARENT_DIR=$(dirname "$SCRIPT_DIR")

# Setup virtual environment without printing to console
VENV_PATH="$PARENT_DIR"/venv
python3 -m venv "$VENV_PATH" &> /dev/null
source "$VENV_PATH"/bin/activate
pip install -r "$PARENT_DIR"/integration-tests/requirements.txt &> /dev/null

export PYTHONPATH="${PARENT_DIR}:${PARENT_DIR}/integration-tests/src:${PARENT_DIR}/api/src"

# Pass include_classes if it's not empty
if [ -z "${INCLUDE_CLASSES}" ]; then
  (cd "$PARENT_DIR"/integration-tests/src && python "$PARENT_DIR"/integration-tests/src/main.py --file_path "${FILE_PATH}" --url "$URL")
else
  (cd "$PARENT_DIR"/integration-tests/src && python "$PARENT_DIR"/integration-tests/src/main.py --file_path "${FILE_PATH}" --url "$URL" --include_classes "${INCLUDE_CLASSES}")
fi
