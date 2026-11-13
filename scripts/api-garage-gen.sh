#!/bin/bash

#
# This script generates the fastapi server stubs for the Garage API. It uses the gen-garage-config.yaml file for
# additional properties.
# For information regarding ignored generated files check the function's .openapi-generator-ignore file.
# As a requirement, you need to execute one time setup-openapi-generator.sh.
# Usage:
#   api-garage-gen.sh
#

GENERATOR_VERSION=7.5.0

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"
GARAGE_PATH=functions-python/garage_api
OPENAPI_SCHEMA=$SCRIPT_PATH/../docs/GarageAPI.yaml
OUTPUT_PATH=$SCRIPT_PATH/../$GARAGE_PATH
CONFIG_FILE=$SCRIPT_PATH/gen-garage-config.yaml

echo "Generating FastAPI server stubs for Garage API from $OPENAPI_SCHEMA to $OUTPUT_PATH"
# Keep the "--global-property apiTests=false" at the end, otherwise it will generate test files that we already have
OPENAPI_GENERATOR_VERSION=$GENERATOR_VERSION $SCRIPT_PATH/bin/openapitools/openapi-generator-cli generate -g python-fastapi \
-i $OPENAPI_SCHEMA  -o $OUTPUT_PATH -c $CONFIG_FILE --global-property apiTests=false
