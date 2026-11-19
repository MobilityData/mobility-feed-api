#!/bin/bash

#
# This script generates the FastAPI server stubs for the Garage API.
# It uses the gen-garage-config.yaml file for additional properties.
# For information regarding ignored generated files check .openapi-generator-ignore file.
# As a requirement, you need to execute one time setup-openapi-generator.sh.
# Usage:
#   api-garage-gen.sh
#

GENERATOR_VERSION=7.5.0

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

OPENAPI_SCHEMA=$SCRIPT_PATH/../docs/GarageAPI.yaml
OPENAPI_SCHEMA_IAP=$SCRIPT_PATH/../docs/GarageAPI_IAP.yaml
OUTPUT_PATH=$SCRIPT_PATH/../api
CONFIG_FILE=$SCRIPT_PATH/gen-garage-config.yaml

sed 's%$ref: "./BearerTokenSchema.yaml#/components/securitySchemes/Authentication"%$ref: "./IAPAuthenticationSchema.yaml#/components/securitySchemes/Authentication"%g' $OPENAPI_SCHEMA > $OPENAPI_SCHEMA_IAP

COMBINED_FILES="$OUTPUT_PATH/.openapi-generator/FILES"
PRE_EXISTING_FILES=$(cat "$COMBINED_FILES" 2>/dev/null || true)

echo "Generating FastAPI server stubs for Garage API from $OPENAPI_SCHEMA to $OUTPUT_PATH"
OPENAPI_GENERATOR_VERSION=$GENERATOR_VERSION $SCRIPT_PATH/bin/openapitools/openapi-generator-cli generate -g python-fastapi \
  -i $OPENAPI_SCHEMA_IAP -o $OUTPUT_PATH -c $CONFIG_FILE --global-property apiTests=false

rm -f $OPENAPI_SCHEMA_IAP

{ echo "$PRE_EXISTING_FILES"; cat "$COMBINED_FILES"; } | awk '!seen[$0]++' > "$COMBINED_FILES.tmp"
mv "$COMBINED_FILES.tmp" "$COMBINED_FILES"
