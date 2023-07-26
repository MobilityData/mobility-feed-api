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

# This script replace variables on an input file creating an output file with the substituted content.
# The script receives the name of the variables as parameters. The variables values as read from the environment.
# The input file must contain the variables in the format {{variable_name}}.
# For an example of a valid input file, check `../infra/vars.tfvars.rename_me`.
# All variables need to be set to the environment previous running the script.
# Parameters:
#   -variables <VARIABLES_LIST>         Comma separated list of variables names.
#   -in_file <INPUT_FULL_PATH_NAME>     Full path and file name of the input file.
#   -out_file <OUTPUT_FULL_PATH_NAME>   Full path and file name of the output file.

display_usage() {
  printf "\nThis script replaces variables from an input file creating/overriding the content of on an output file"
  printf "\nScript Usage:\n"
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  -variables <VARIABLES_LIST>         Comma separated list of variables names."
  echo "  -in_file <INPUT_FULL_PATH_NAME>     Full path and file name of the input file."
  echo "  -out_file <OUTPUT_FULL_PATH_NAME>   Full path and file name of the output file."
  echo "  -help                               Display help content."
  exit 1
}

VARIABLES=""
INPUT_FILE=""
OUT_FILE=""

while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
    -variables)
      VARIABLES="$2"
      shift # past argument
      shift # past value
      ;;
    -in_file)
      IN_FILE="$2"
      shift # past argument
      shift # past value
      ;;
    -out_file)
      OUT_FILE="$2"
      shift # past argument
      shift # past value
      ;;
    -h|--help)
      display_usage
      ;;
    *) # unknown option
      shift # past argument
      ;;
  esac
done

if [[ -z "${VARIABLES}" || -z "${IN_FILE}" || -z "${OUT_FILE}" ]]; then
  echo "Missing required parameters."
  display_usage
fi

if [[ ! -f $IN_FILE ]]
then
    echo "Input file does not exist, name: $IN_FILE"
    echo "Bye for now."
    exit 1
fi

if [[ -f $OUT_FILE ]]
then
    echo "Warn: Output file does exist and will be overriden, name: $OUT_FILE"
fi

list=$(echo "$VARIABLES" | tr "," "\n")

#  Check if all variables are set
for varname in $list
do
    if [[ -z "${!varname}" ]]; then
      echo "Missing required variable value with name: $varname."
      echo "Script will not execute variables replacement, bye for now."
      exit 1
    fi
done

# Reads from input setting the first version of the output.
output=$(<"$IN_FILE")

# Replace variables and create output file
for varname in $list
do
    # shellcheck disable=SC2001
    # shellcheck disable=SC2016
    output=$(echo "$output" | sed  's/{{'"$varname"'}}/'\""${!varname}"\"'/g')
done

echo "$output" > "$OUT_FILE"