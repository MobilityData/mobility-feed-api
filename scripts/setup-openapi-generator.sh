#!/bin/bash

# relative
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

export OPENAPI_GENERATOR_VERSION=7.0.0-beta
mkdir -p $SCRIPT_PATH/bin/openapitools
curl https://raw.githubusercontent.com/OpenAPITools/openapi-generator/master/bin/utils/openapi-generator-cli.sh > $SCRIPT_PATH/bin/openapitools/openapi-generator-cli
chmod u+x $SCRIPT_PATH/bin/openapitools/openapi-generator-cli