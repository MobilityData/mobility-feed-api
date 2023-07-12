#!/bin/bash


# Fixing generators version to have consistent generation
BETA_VERSION=7.0.0-beta
STABLE_VERSION=6.6.0

## Few fixes introduced in the latest(beta still 2023/07/12) improving the python-fastapi generation.
## More info,
##      https://github.com/OpenAPITools/openapi-generator/issues/13863
##      https://github.com/OpenAPITools/openapi-generator/issues/13863
GENERATOR_VERSION=$BETA_VERSION

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

OPENAPI_SCHEMA=$SCRIPT_PATH/../docs/DatabaseCatalogAPI.yaml
OUTPUT_PATH=$SCRIPT_PATH/../api
CONFIG_FILE=$SCRIPT_PATH/gen-config.yaml
OPENAPI_GENERATOR_VERSION=$GENERATOR_VERSION $SCRIPT_PATH/bin/openapitools/openapi-generator-cli generate -g python-fastapi -i $OPENAPI_SCHEMA  -o $OUTPUT_PATH -c $CONFIG_FILE