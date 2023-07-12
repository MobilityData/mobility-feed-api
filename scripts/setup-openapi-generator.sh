#!/bin/bash

#
# This script downloads the openapi-generator-cli.sh locally.
# The openapi-generator-cli.sh helps to switch the generator's versions and make the generation process CI-friendly.
# More info, https://github.com/OpenAPITools/openapi-generator/blob/master/bin/utils/openapi-generator-cli.sh 
#

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

mkdir -p $SCRIPT_PATH/bin/openapitools
curl https://raw.githubusercontent.com/OpenAPITools/openapi-generator/master/bin/utils/openapi-generator-cli.sh > $SCRIPT_PATH/bin/openapitools/openapi-generator-cli
chmod u+x $SCRIPT_PATH/bin/openapitools/openapi-generator-cli