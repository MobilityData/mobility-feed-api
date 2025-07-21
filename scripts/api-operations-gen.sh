#!/bin/bash

#
# This script generates the fastapi server stubs. It uses the gen-config.yaml file for additional properties.
# For information regarding ignored generated files check .openapi-generator-ignore file.
# As a requirement, you need to execute one time setup-openapi-generator.sh.
# Usage:
#   api-gen.sh
#

GENERATOR_VERSION=7.10.0

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"
OPERATIONS_PATH=functions-python/operations_api
OPENAPI_SCHEMA=$SCRIPT_PATH/../docs/OperationsAPI.yaml
OUTPUT_PATH=$SCRIPT_PATH/../$OPERATIONS_PATH
CONFIG_FILE=$SCRIPT_PATH/gen-operations-config.yaml

echo "Generating FastAPI server stubs for Operations API from $OPENAPI_SCHEMA to $OUTPUT_PATH" 
# Keep the "--global-property apiTests=false" at the end, otherwise it will generate test files that we already have
OPENAPI_GENERATOR_VERSION=$GENERATOR_VERSION $SCRIPT_PATH/bin/openapitools/openapi-generator-cli generate -g python-fastapi \
-i $OPENAPI_SCHEMA  -o $OUTPUT_PATH -c $CONFIG_FILE --global-property apiTests=false

