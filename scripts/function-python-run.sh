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

# Executes the python function passed as argument supported by the functions-framework.
# The script receives the name of the function as parameter.
# The function must be located in the folder `functions-python/<function_name>`.
# The function must be defined in the file `functions-python/<function_name>/main.py`.
# The script look for a `.env.local` file in the function's folder to load environment variables.
# Use --env_file to load a different one, e.g. a file pointing the function at another database.

# Usage:
#   function-python-run.sh --function_name <function name> [--env_file <file>]
# Example:
#   function-python-run.sh --function_name tokens
#   function-python-run.sh --function_name tasks_executor --env_file config/.env.dupdb

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"
FUNCTIONS_PATH="$SCRIPT_PATH/../functions-python"

# function printing usage
display_usage() {
  printf "\nThis script executes a python function"
  printf "\nScript Usage:\n"
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  -h|--help                           Display help content."
  echo "  --function_name <FUNCTION_NAME>     Name of the function to be executed."
  echo "  --index <integer>                   One based index of the function to be executed, if more than one function are decorated."
  echo "  --no_install_venv                   Do not install a python virtual environment."
  echo "  --env_file <FILE>                   Environment file to load. Absolute, or relative to the"
  echo "                                      function's folder, then to the repo root. Default .env.local."
  exit 1
}

index=1
function_name=''
env_file='.env.local'

while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
  -h | --help)
    display_usage
    exit 0
    ;;
  --function_name)
    function_name="$2"
    shift # past argument
    shift # past value
    ;;
  --index)
    index="$2"
    shift # past argument
    shift # past value
    ;;
  --no_install_venv)
    no_install_venv=true
    shift # past argument
    ;;
  --env_file)
    env_file="$2"
    env_file_explicit=true
    shift # past argument
    shift # past value
    ;;
  *)      # unknown option
    shift # past argument
    ;;
  esac
done

FX_PATH="$FUNCTIONS_PATH/$function_name/src"

if [ ! -d "$FX_PATH" ]; then
  printf "\nERROR: function's folder not found at location: %s\n" "$FX_PATH"
  display_usage
  exit 1
fi

# A relative path is the function's own folder first - that is where .env.local lives - then
# the repo root, so a shared file can be named as `config/.env.<something>`.
case "$env_file" in
/*) ENV_FILE="$env_file" ;;
*)
  ENV_FILE="$FX_PATH/../$env_file"
  if [ ! -f "$ENV_FILE" ] && [ -f "$SCRIPT_PATH/../$env_file" ]; then
    ENV_FILE="$SCRIPT_PATH/../$env_file"
  fi
  ;;
esac

if [ ! -f "$ENV_FILE" ]; then
  # An env file asked for by name is a deliberate choice - usually pointing the function at
  # another database - so falling back to the default would run against the wrong one silently.
  if [ "${env_file_explicit:-}" = "true" ]; then
    printf "\nERROR: env file not found at location: %s\n" "$ENV_FILE"
    exit 1
  fi
  printf "\nWARN: %s file not found at location: %s\n" "$env_file" "$ENV_FILE"
else
  printf "\nINFO: loading environment variables from: %s\n" "$ENV_FILE"
  while IFS= read -r line || [ -n "$line" ]
  do
    # Skip blanks, comments and anything that is not KEY=VALUE: exporting those fails with a
    # confusing message naming whatever the line happened to contain.
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      export "$line"
    fi
  done < "$ENV_FILE"
fi

# extract the --target value from the function's name main.py file with @functions_framework.http annotation
target=$(grep -zoE "@functions_framework\.http\s*\n\s*def [a-zA-Z_][a-zA-Z_0-9]*" "$FX_PATH/main.py" \
  | grep -oE "def [a-zA-Z_][a-zA-Z_0-9]*" \
  | cut -d ' ' -f 2 \
  | sed -n "${index}p")

# verify if the target is not empty
if [ -z "$target" ]; then
  printf "\nERROR: function's main.py file does not contain a @functions_framework.http annotation or wrong index"
  display_usage
  exit 1
fi

export PYTHONPATH="$FX_PATH"

# We can skp the venv install if it has already been done. It saves time when repetitively running this script.
if [ "${no_install_venv:-}" != "true" ]; then
  # Install a virgin python virtual environment and provision it with the required packages so it's the same as
  # the one that will be deployed in the cloud
  pushd "$FUNCTIONS_PATH/$function_name" >/dev/null
  printf "\nINFO: installing python virtual environment"
  rm -rf venv
  pip3 install --disable-pip-version-check virtualenv > /dev/null
  python3 -m virtualenv venv > /dev/null
  venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt >/dev/null
  popd > /dev/null
else
  printf "\nINFO: skipping python virtual environment installation"
fi

printf "\nINFO: running function in functions-framework"
"$FUNCTIONS_PATH/$function_name"/venv/bin/functions-framework --target "$target" --debug --source "$FX_PATH/main.py" --signature-type http
