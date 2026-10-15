#!/bin/bash

#
# This script generates the FastAPI server stubs for the User Service API.
# It uses the gen-user-service-config.yaml file for additional properties.
# For information regarding ignored generated files check .openapi-generator-ignore file.
# As a requirement, you need to execute one time setup-openapi-generator.sh.
# Usage:
#   api-user-service-gen.sh
#

GENERATOR_VERSION=7.5.0

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

OPENAPI_SCHEMA=$SCRIPT_PATH/../docs/UserServiceAPI.yaml
OPENAPI_SCHEMA_IAP=$SCRIPT_PATH/../docs/UserServiceAPI_IAP.yaml
OUTPUT_PATH=$SCRIPT_PATH/../api
CONFIG_FILE=$SCRIPT_PATH/gen-user-service-config.yaml

sed 's%$ref: "./BearerTokenSchema.yaml#/components/securitySchemes/Authentication"%$ref: "./IAPAuthenticationSchema.yaml#/components/securitySchemes/Authentication"%g' $OPENAPI_SCHEMA > $OPENAPI_SCHEMA_IAP

# Preserve the feeds-generator FILES list before this generator overwrites it,
# then merge both lists so all generated files remain tracked.
COMBINED_FILES="$OUTPUT_PATH/.openapi-generator/FILES"
PRE_EXISTING_FILES=$(cat "$COMBINED_FILES" 2>/dev/null || true)

echo "Generating FastAPI server stubs for User Service API from $OPENAPI_SCHEMA to $OUTPUT_PATH"
# Keep the "--global-property apiTests=false" at the end, otherwise it will generate test files that we already have
OPENAPI_GENERATOR_VERSION=$GENERATOR_VERSION $SCRIPT_PATH/bin/openapitools/openapi-generator-cli generate -g python-fastapi \
  -i $OPENAPI_SCHEMA_IAP -o $OUTPUT_PATH -c $CONFIG_FILE --global-property apiTests=false

rm -f $OPENAPI_SCHEMA_IAP

# Re-merge: restore pre-existing entries then append any new user-service entries,
# preserving original order and removing duplicates.
{ echo "$PRE_EXISTING_FILES"; cat "$COMBINED_FILES"; } | awk '!seen[$0]++' > "$COMBINED_FILES.tmp"
mv "$COMBINED_FILES.tmp" "$COMBINED_FILES"
