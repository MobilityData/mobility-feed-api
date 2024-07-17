#!/bin/bash

#
# This script generates the fastapi server stubs. It uses the gen-config.yaml file for additional properties.
# For information regarding ignored generated files check .openapi-generator-ignore file.
# As a requirement, you need to execute one time setup-openapi-generator.sh.
# Usage:
#   api-gen.sh
#

GENERATOR_VERSION=7.5.0

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

OPENAPI_SCHEMA=$SCRIPT_PATH/../docs/DatabaseCatalogAPI.yaml
OPENAPI_SCHEMA_IAP=$SCRIPT_PATH/../docs/DatabaseCatalogAPI_IAP.yaml
OUTPUT_PATH=$SCRIPT_PATH/../api
CONFIG_FILE=$SCRIPT_PATH/gen-config.yaml

sed 's%$ref: "./BearerTokenSchema.yaml#/components/securitySchemes/Authentication"%$ref: "./IAPAuthenticationSchema.yaml#/components/securitySchemes/Authentication"%g' $OPENAPI_SCHEMA > $OPENAPI_SCHEMA_IAP

OPENAPI_GENERATOR_VERSION=$GENERATOR_VERSION $SCRIPT_PATH/bin/openapitools/openapi-generator-cli generate -g python-fastapi -i $OPENAPI_SCHEMA_IAP  -o $OUTPUT_PATH -c $CONFIG_FILE --global-property apiTests=false

rm -f $OPENAPI_SCHEMA_IAP