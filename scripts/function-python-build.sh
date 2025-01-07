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

# Build a python function compressing the source code and its dependencies excluding the libs in requirements.txt.
# The script receives the name of the function as parameter.
# The function must be located in the folder `functions-python/<function_name>`.
# The function config must be defined in the file `functions-python/<function_name>/function_config.json`.

# Usage:
#   function-python-build.sh --function_name <function name> --all
# Examples:
#   function-python-build.sh --function_name tokens
#   function-python-build.sh --all

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"
ROOT_PATH="$SCRIPT_PATH/.."
FUNCTIONS_PATH="$ROOT_PATH/functions-python"
API_SRC_PATH="$ROOT_PATH/api/src"

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
  FX_CONFIG_FILE="$FX_PATH/function_config.json"

  # verify if the function's folder exists
  if [ ! -d "$FX_PATH" ]; then
    printf "\nERROR: function's folder \"$FX_PATH\" does not exist"
    display_usage
    exit 1
  fi

  # verify that the function config file exists
   if [ ! -f "$FX_CONFIG_FILE" ]; then
    printf "\nERROR: function's config file \"$FX_CONFIG_FILE\" does not exist"
    display_usage
    exit 1
  fi

  # include folders that are in the src function_config file as a json property called "include_folders"
  include_folders=$(jq -r .include_folders[] $FX_CONFIG_FILE 2> /dev/null)
  # And include_api_folders (if any). These will be taken from api/src
  include_api_folders=$(jq -r '.include_api_folders[]' $FX_CONFIG_FILE 2> /dev/null)

  # We'll assume that we build only if there is an entry_point defined.
  if jq -e '.entry_point' "$FX_CONFIG_FILE" > /dev/null; then
    rm -rf "$FX_DIST_PATH"
    mkdir "$FX_DIST_PATH"

    # Run pre_build script if specified
    pre_build_script=$(jq -r '.build_settings.pre_build_script // empty' "$FX_PATH/function_config.json")
    if [ -n "$pre_build_script" ]; then
      printf "\nRunning pre_build script: $pre_build_script\n"
      (cd "$FX_PATH" && eval "$pre_build_script")
      printf "\nCompleted running pre_build script\n"
    fi

     # Use rsync instead of cp -R to exclude some directories that are not useful for deployment
     rsync -av --exclude 'shared' --exclude 'test_shared' "$FX_SOURCE_PATH/" "$FX_DIST_BUILD/"
     cp "$FX_PATH/requirements.txt" "$FX_DIST_BUILD"

     copy_folders_to_build $FUNCTIONS_PATH "$include_folders" "include_folders"
     copy_folders_to_build $API_SRC_PATH "$include_api_folders" "include_api_folders"

     (cd "$FX_DIST_BUILD" && zip -r -X "../$function_name.zip" . >/dev/null)
  fi

  printf "\nCompleted building function $function_name\n"
}

copy_folders_to_build() {
  root_folder=$1
  folders=$2
  property=$3
  if [ -z "$folders" ]; then
    printf "\nINFO: function_config.json file does not contain a property called $property\n"
  else
    printf "\nINFO: function_config.json file contains a property called $property\n"
  fi
  for folder in $folders; do

    printf "\nINFO: Including .py and .json files from folder $root_folder/$folder, excluding 'tests' and 'venv' directories\n"
    # Find all .py and .json files, excluding those in 'tests' or 'venv' directories
    if [ ! -e $root_folder/$folder ]; then
      echo "ERROR ---> Folder $root_folder/$folder does not exist"
      continue
    fi
    (
      cd "$root_folder" &&
        find "$folder" \
          \( -type d \( -name "tests" -o -name "venv" -o -name "shared" -o -name "test_shared" \) \) -prune -o \
          \( -name "*.py" -o -name "*.json" \) -print
    ) | while read file; do

        if [ -d "$root_folder/$file" ]; then continue; fi
        dest_path="$FX_DIST_BUILD/shared/$file"
        # Create the directory structure for the current file in the destination
        mkdir -p "$(dirname "$dest_path")"

        # Copy the file to the destination
        cp "$root_folder/$file" "$dest_path"
    done

  done
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
