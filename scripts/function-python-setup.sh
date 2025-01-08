#
#  MobilityData 2024
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

# Link all the necessary packages in one or many python functions so they can run self contained.
# The script will link all the folders defined in the function_config.json file in the property "include_folders" and
# "include_api_folders.
# All linked libraries will be in functions-python/<function_name>/src/shared.
# To run or test the functions, you need to add the folder to PYTHONPATH.
# The script receives the name of the function as parameter.
# The function must be located in the folder `functions-python/<function_name>`.
# The function config must be defined in the file `functions-python/<function_name>/function_config.json`.

# Usage:
#   function-python-setup.sh --function_name <function name> --all
# Examples:
#   function-python-setup.sh --function_name batch_datasets
#   function-python-setup.sh --all

SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"
ROOT_PATH=$(realpath "$SCRIPT_PATH/..")
FUNCTIONS_PATH="$ROOT_PATH/functions-python"
API_PATH="$ROOT_PATH/api/src"

# function printing usage
display_usage() {
  printf "\nThis script links packages related to a python function in folders shared and test_shared in the function's src and tests folder"
  printf "\nso they are available when running the tests."
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
CLEAN='false'
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
  --clean)
    CLEAN="true"
    shift
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

setup_function() {
  function_name=$1
  # Remove ending / if any
  function_name=${function_name%/}
  echo "Setting up function $function_name"
  # verify if the function's folder exists
  if [ ! -d "$FUNCTIONS_PATH/$function_name" ]; then
    echo "ERROR: function's folder does not exist"
    display_usage
    exit 1
  fi

  FX_PATH="$FUNCTIONS_PATH/$function_name"
  FX_SOURCE_PATH="$FUNCTIONS_PATH/$function_name/src"
  FX_TEST_SOURCE_PATH="$FUNCTIONS_PATH/$function_name/tests"
  FX_CONFIG_FILE="$FX_PATH/function_config.json"
  TEST_CONFIG_FILE="$FX_PATH/test_config.json"

  # verify if the function's folder exists
  if [ ! -d "$FX_PATH" ]; then
    echo "ERROR: function's folder \"$FX_PATH\" does not exist"
    display_usage
    exit 1
  fi

  # verify that the function config file exists
  if [ -f "$FX_CONFIG_FILE" ]; then
    # Collect folders specified with "include_folders" and "include_api_folders" of function_config.json
    include_folders=$(jq -r .include_folders[] $FX_CONFIG_FILE 2> /dev/null)
    include_api_folders=$(jq -r '.include_api_folders[]' $FX_CONFIG_FILE 2> /dev/null)
  elif [ -f "$TEST_CONFIG_FILE" ]; then
    # The folder is not a function since it does not have a function_config.json.
    # But maybe some tests have are to be run and they might need folders.
    include_folders=$(jq -r .include_folders[] $TEST_CONFIG_FILE 2> /dev/null)
    include_api_folders=$(jq -r '.include_api_folders[]' $TEST_CONFIG_FILE 2> /dev/null)
  else
    echo "Config file \"$FX_CONFIG_FILE\" does not exist, no setting up to do."
    exit 0
  fi

  dst_folder="$FX_SOURCE_PATH/shared"
  rm -rf "$dst_folder"
  mkdir -p "$dst_folder"
  create_symbolic_links "$FUNCTIONS_PATH" "$include_folders" "$dst_folder"
  create_symbolic_links "$API_PATH" "$include_api_folders" "$dst_folder"

  # We'll hardcode all the shared packages that are needed for testing
  dst_folder="$FX_TEST_SOURCE_PATH/test_shared"
  rm -rf "$dst_folder"/*
  rmdir "$dst_folder"
  mkdir -p "$dst_folder"
  create_symbolic_links "$FUNCTIONS_PATH" "test_utils" "$dst_folder"

}

create_symbolic_links() {
  root_folder=$1
  folders=$2
  dst_folder=$3

  if [ -z "$folders" ]; then
    return
  fi

  for folder in $folders; do
    src_folder="$root_folder/$folder"
    if [[ "$dst_folder" != "$src_folder"* ]]; then
      relative_path=$(python3 -c "import os.path; print(os.path.relpath(\"$src_folder\", \"$dst_folder\"))")
      echo "INFO: Linking $relative_path to $dst_folder"
      (cd $dst_folder && ln -s $relative_path)
    else
      echo "INFO: $dst_folder is a descendant of $src_folder, skipping"
    fi
  done
}

clean_shared_folders() {
  function_name=$1
  # Remove ending / if any
  function_name=${function_name%/}
  echo "INFO: Cleaning shared folders for function $function_name"
  rm "$FUNCTIONS_PATH/$function_name/src/shared/"* > /dev/null 2>&1
  rmdir "$FUNCTIONS_PATH/$function_name/src/shared" > /dev/null 2>&1
  rm "$FUNCTIONS_PATH/$function_name/src/test_shared/"* > /dev/null 2>&1
  rmdir "$FUNCTIONS_PATH/$function_name/src/test_shared" > /dev/null 2>&1
}

if [ "$ALL" = "true" ]; then
  # get all the functions in the functions-python folder that contain a function_config.json file
  for function in $(find "$FUNCTIONS_PATH" -maxdepth 2 -name "function_config.json"); do
    function_name=$(echo "$function" | rev | cut -d '/' -f 2 | rev)
    if [ "$CLEAN" = "true" ]; then
      clean_shared_folders $function_name
    else
      setup_function $function_name
    fi
  done
else
  if [ -z "$FX_NAME_PARAM" ]; then
    printf "\nERROR: function name not provided"
    display_usage
    exit 1
  fi
  if [ "$CLEAN" = "true" ]; then
    clean_shared_folders $FX_NAME_PARAM
  else
    setup_function $FX_NAME_PARAM
  fi
fi
