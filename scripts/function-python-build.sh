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

# Build a python function compressing the source code and it's dependencies exluding the libs in requirements.txt.
# The script receives the name of the function as parameter.
# The function must be located in the folder `functions-python/<function_name>`.
# The function config must be defined in the file `functions-python/<function_name>/function_config.json`.

# Usage:
#   python-function-build.sh --function_name <function name> --all
# Examples:
#   python-function-build.sh --function_name tokens
#   python-function-build.sh --all

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
  echo "  --all                               Build all functions."
  exit 1
}

FX_NAME_PARAM=''
ALL='false'
while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
  -h | --help)
    display_usage
    exit 0
    ;;
  --all)
    ALL="true"
    shift # past argument
    ;;
  --function_name)
    FX_NAME_PARAM="$2"
    shift # past argument
    shift # past value
    ;;
  *)      # unknown option
    shift # past argument
    ;;
  esac
done

# --all and --function_name are mutually exclusive
if [ "$ALL" = "true" ] && [ ! -z "$FX_NAME_PARAM" ]; then
  printf "\nERROR: --all and --function_name are mutually exclusive"
  display_usage
  exit 1
fi

build_function() {
  function_name=$1
  printf "\nBuilding function $function_name"
  # verify if the function's folder exists
  if [ ! -d "$FUNCTIONS_PATH/$function_name" ]; then
    printf "\nERROR: function's folder does not exist"
    display_usage
    exit 1
  fi

  FX_PATH="$FUNCTIONS_PATH/$function_name"
  FX_SOURCE_PATH="$FUNCTIONS_PATH/$function_name/src"
  FX_DIST_PATH="$FX_PATH/.dist"
  FX_DIST_BUILD="$FX_DIST_PATH/build"

  rm -rf "$FX_DIST_PATH"
  mkdir "$FX_DIST_PATH"

  cp -R "$FX_SOURCE_PATH" "$FX_DIST_BUILD"
  cp "$FX_PATH/requirements.txt" "$FX_DIST_BUILD"

  # include folders that are in the src function_config file as a json property called "include_folders"
  include_folders=$(cat "$FX_PATH/function_config.json" | jq -r '.include_folders[]')
  if [ -z "$include_folders" ]; then
    printf "\nINFO: function_config.json file does not contain a property called include_folders"
  else
    printf "\nINFO: function_config.json file contains a property called include_folders"
  fi
  for folder in $include_folders; do
    cp -R "$FX_PATH/$folder" "$FX_DIST_BUILD"
  done

  (cd "$FX_DIST_BUILD" && zip -r -X "../$function_name.zip" . >/dev/null)
  printf "\nCompleted building function $function_name\n"
}

if [ "$ALL" = "true" ]; then
  # get all the functions in the functions-python folder that contain a function_config.json file
  for function in $(find "$FUNCTIONS_PATH" -maxdepth 2 -name "function_config.json"); do
    function_name=$(echo "$function" | rev | cut -d '/' -f 2 | rev)
    build_function $function_name
  done
else
  if [ -z "$FX_NAME_PARAM" ]; then
    printf "\nERROR: function name not provided"
    display_usage
    exit 1
  fi
  build_function $FX_NAME_PARAM
fi
