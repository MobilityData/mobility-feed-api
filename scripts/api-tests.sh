#!/bin/bash

#
# This script executes all project tests and generates coverage reports.
# By default all tests are executed, if you need to execute a single test file, pass the test file name as a parameter.
# All test are expected to be inside the directory <project_folder>/tests.
# Usage:
#   api-test.sh <optional_test_file>
#
# Parameters:
# <test_file>: optional

# absolute path
ABS_SCRIPTPATH="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
TEST_FILE=""
FOLDER=""

# funtion to display usage
display_usage() {
  printf "\nThis script executes all project tests.\n"
  printf "\nScript Usage:\n"
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  -test_file <TEST_FILE>   Test file name to be executed."
  echo "  -folder <FOLDER>         Folder name to be executed."
  echo "  -help                    Display help content."
  exit 1
}

while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
  --help)
    display_usage
    ;;
  --test_file)
    TEST_FILE="$2"
    shift # past argument
    shift # past value
    ;;
  --folder)
    FOLDER="$2"
    shift # past argument
    shift # past value
    ;;
  *)      # unknown option
    shift # past argument
    ;;
  esac
done

cat $ABS_SCRIPTPATH/../config/.env.local > $ABS_SCRIPTPATH/../.env

execute_tests() {
  printf "\nExecuting tests in $1\n"
  cd $ABS_SCRIPTPATH/$1/ || exit 1
  pip3 install --disable-pip-version-check virtualenv >/dev/null
  python -m virtualenv venv >/dev/null
  venv/bin/python -m pip install -r requirements.txt >/dev/null
  venv/bin/python -m pip install -r requirements_dev.txt >/dev/null
  venv/bin/python -m pip install coverage >/dev/null  # Install coverage if not already installed

  # Run tests with coverage
  venv/bin/coverage run -m pytest -W 'ignore::DeprecationWarning' tests

  # Generate coverage report
  current_dir_name=$(basename "$(pwd)")
  mkdir $ABS_SCRIPTPATH/coverage_reports/$current_dir_name
  venv/bin/coverage report > $ABS_SCRIPTPATH/coverage_reports/$current_dir_name/report.txt
  echo "** COVERAGE REPORT FOR $1 **"
  cat $ABS_SCRIPTPATH/coverage_reports/$current_dir_name/report.txt

  # Fail if tests fail
  if [ $? -ne 0 ]; then
    printf "\nTests failed in $1\n"
    exit 1
  fi  
  printf "\n"
}

if [[ ! -z "${TEST_FILE}" && ! -z "${FOLDER}" ]]; then
  echo "The parameters -test_file and -folder are mutually exclusive."
  exit 1
fi

execute_python_tests() {
  printf "\nExecuting python tests in $1\n"
  cd $ABS_SCRIPTPATH/../$1
  export PYTHONPATH="$ABS_SCRIPTPATH/../functions-python:$PYTHONPATH"
  printf "PYTHONPATH=$PYTHONPATH\n"
  for file in */; do
    if [[ -d "$file" && ! -L "$file" ]]; then
      if [[ -d "$file/tests" ]]; then
        (execute_tests "../functions-python/$file")
        # Fail if tests fail
        if [ $? -ne 0 ]; then
          printf "\nTests failed in $1\n"
          exit 1
        fi        
      fi
      if [[ "$file" == "tests/" ]]; then
        (execute_tests "../$1")
        # Fail if tests fail
        if [ $? -ne 0 ]; then
          printf "\nTests failed in $1\n"
          exit 1
        fi        
      fi
    fi
  done
}

# if no parameters is passed, execute all API tests
if [[ -z "${FOLDER}" ]] && [[ -z "${TEST_FILE}" ]]; then
  execute_tests "../api"
  exit 1
fi

if [[ ! -z "${TEST_FILE}" ]]; then
  execute_tests "../$TEST_FILE"
  exit 0
fi

if [[ ! -z "${FOLDER}" ]]; then
  # if folder starts with functions-python, execute python tests
  if [[ "${FOLDER}" == "functions-python"* ]]; then
    execute_python_tests "$FOLDER"
  else
    execute_tests "../$FOLDER"
  fi
fi

