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
# The script receives the name of the variables as parameters. The variables values are read from the environment.
# The input file must contain the variables in the format {{variable_name}}.
# For an example of a valid input file, check `../infra/vars.tfvars.rename_me`.
# All variables need to be set to the environment previous running the script.
# Parameters:
#   -variables <VARIABLES_LIST>           Comma separated list of REQUIRED variable names.
#   -optional_variables <OPTIONAL_LIST>   Comma separated list of OPTIONAL variable names (may be unset or empty).
#   -in_file <INPUT_FULL_PATH_NAME>       Full path and file name of the input file.
#   -out_file <OUTPUT_FULL_PATH_NAME>     Full path and file name of the output file.
#   -no_quotes                            Option to disable enclosing variable in double quotes during substitution

display_usage() {
  printf "\nThis script replaces variables from an input file creating/overriding the content of on an output file"
  printf "\nScript Usage:\n"
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  -variables <VARIABLES_LIST>         Comma separated list of REQUIRED variable names."
  echo "  -optional_variables <OPTIONAL_LIST> Comma separated list of OPTIONAL variable names."
  echo "  -in_file <INPUT_FULL_PATH_NAME>     Full path and file name of the input file."
  echo "  -out_file <OUTPUT_FULL_PATH_NAME>   Full path and file name of the output file."
  echo "  -no_quotes                          Do not enclose variable values with quotes."
  echo "  -help                               Display help content."
  exit 1
}

VARIABLES=""
OPTIONAL_VARIABLES=""
INPUT_FILE=""
OUT_FILE=""
ADD_QUOTES="true"

while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
    -variables)
      VARIABLES="$2"
      shift # past argument
      shift # past value
      ;;
    -optional_variables)
      OPTIONAL_VARIABLES="$2"
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
    -no_quotes)
      ADD_QUOTES="false"
      shift # past argument
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
optional_list=$(echo "$OPTIONAL_VARIABLES" | tr "," "\n")

#  Check required variables (optional ones may be unset or empty)
for varname in $list; do
  if [[ -z "${!varname+x}" ]]; then
    echo "Missing required variable (unset) with name: $varname."
    echo "Script will not execute variables replacement, bye for now."
    exit 1
  fi
  if [[ -z "${!varname}" ]]; then
    echo "Missing required variable (empty value) with name: $varname."
    echo "Script will not execute variables replacement, bye for now."
    exit 1
  fi
done

# Reads from input setting the first version of the output.
output=$(<"$IN_FILE")

# Replace variables and create output file
for varname in $list; do
  # Required variables are guaranteed non-empty here
  value="${!varname}"
  # shellcheck disable=SC2001
  # shellcheck disable=SC2016
  if [[ "$ADD_QUOTES" == "true" ]]; then
    output=$(echo "$output" | sed 's|{{'"$varname"'}}|'"\"$value\""'|g')
  else
    output=$(echo "$output" | sed 's|{{'"$varname"'}}|'"$value"'|g')
  fi
done

# Substitute optional variables only when they have a non-empty value
for varname in $optional_list; do
  # Skip empty or unset optional vars (leave placeholder intact)
  if [[ -z "${!varname+x}" || -z "${!varname}" ]]; then
    continue
  fi
  value="${!varname}"
  if [[ "$ADD_QUOTES" == "true" ]]; then
    output=$(echo "$output" | sed 's|{{'"$varname"'}}|'"\"$value\""'|g')
  else
    output=$(echo "$output" | sed 's|{{'"$varname"'}}|'"$value"'|g')
  fi
done

echo "$output" > "$OUT_FILE"
