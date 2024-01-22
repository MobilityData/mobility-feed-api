#!/bin/bash

#
# This script executes all project tests and generates coverage reports.
#
# Usage:
#   api-test.sh [options]
#
# Options:
#   -test_file <TEST_FILE> : Execute a specific test file. (optional)
#   -folder <FOLDER>       : Execute tests in a specific folder. (optional)
#   -html_report           : Generate an HTML coverage report in addition to the standard report. (optional)
#   -help                  : Display this help content.
#
# By default, without any options, the script executes all tests within the <project_folder>/tests
# directory and generates a coverage report. If the -html_report option is used, an additional HTML
# report will be generated in the coverage_reports directory, providing a visual representation of
# the coverage.
#
# Examples:
#   Execute all tests and generate standard coverage report:
#     ./api-test.sh
#
#   Execute tests in a specific folder and generate both standard and HTML coverage reports:
#     ./api-test.sh --folder <FOLDER> --html_report
#
#   Execute a specific test file:
#     ./api-test.sh --test_file <TEST_FILE>



# absolute path
ABS_SCRIPTPATH="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
TEST_FILE=""
FOLDER=""
HTML_REPORT=false
COVERAGE_THRESHOLD=84

# color codes for easier reading
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color


# function to display usage
display_usage() {
  printf "\nThis script executes all project tests.\n"
  printf "\nScript Usage:\n"
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  -test_file <TEST_FILE>   Test file name to be executed."
  echo "  -folder <FOLDER>         Folder name to be executed."
  echo "  -html_report             Generate HTML coverage report."
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
  --html_report)
    HTML_REPORT=true
    shift # past argument
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
  python3 -m virtualenv venv >/dev/null
  venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt >/dev/null
  venv/bin/python -m pip install --disable-pip-version-check -r requirements_dev.txt >/dev/null
  venv/bin/python -m pip install --disable-pip-version-check coverage >/dev/null

  # Run tests with coverage
  venv/bin/coverage run --branch -m pytest -W 'ignore::DeprecationWarning' tests

  # Fail if tests fail
  if [ $? -ne 0 ]; then
    printf "\n${RED}Tests failed in $1${NC}\n"
    exit 1
  fi

  # Generate coverage report
  current_dir_name=$(basename "$(pwd)")
  mkdir $ABS_SCRIPTPATH/coverage_reports
  mkdir $ABS_SCRIPTPATH/coverage_reports/$current_dir_name
  venv/bin/coverage report > $ABS_SCRIPTPATH/coverage_reports/$current_dir_name/report.txt
  printf "\n${YELLOW}COVERAGE REPORT FOR $1:${NC}\n"
  cat $ABS_SCRIPTPATH/coverage_reports/$current_dir_name/report.txt

  # Generate HTML coverage report if requested
  if [ "$HTML_REPORT" = true ]; then
    venv/bin/coverage html -d $ABS_SCRIPTPATH/coverage_reports/$current_dir_name/html
  fi

  # Extract the total coverage percentage
  coverage_percentage=$(venv/bin/coverage report | grep 'TOTAL' | awk '{print $NF}' | sed 's/%//')
  printf "Current branch coverage is $coverage_percentage%%\n"

  # Fail if branch coverage is under the threshold
  if [ "$coverage_percentage" -lt "$COVERAGE_THRESHOLD" ]; then
    printf "\n${RED}Branch coverage of $coverage_percentage%% is below the $COVERAGE_THRESHOLD%% threshold${NC}\n"
    exit 1
  fi
  printf "\n${GREEN}Branch coverage of $coverage_percentage%% is above or equal to the $COVERAGE_THRESHOLD%% threshold${NC}\n"
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
          printf "\n${RED}Failure in $1\n${NC}"
          exit 1
        fi        
      fi
      if [[ "$file" == "tests/" ]]; then
        (execute_tests "../$1")
        # Fail if tests fail
        if [ $? -ne 0 ]; then
          printf "\n${RED}Failure in $1\n${NC}"
          exit 1
        fi        
      fi
    fi
  done
}

# if no parameters is passed, execute all API tests
if [[ -z "${FOLDER}" ]] && [[ -z "${TEST_FILE}" ]]; then
  execute_tests "../api"
fi

if [[ ! -z "${TEST_FILE}" ]]; then
  execute_tests "../$TEST_FILE"
fi

if [[ ! -z "${FOLDER}" ]]; then
  if [[ "${FOLDER}" == "functions-python"* ]]; then
    execute_python_tests "$FOLDER"
  else
    execute_tests "../$FOLDER"
  fi
fi

printf "\n${GREEN}All tests passed successfully.${NC}\n"
exit 0
