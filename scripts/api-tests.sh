#!/bin/bash

#
# This script executes all project tests.
# By default all tests are executed, if you need to execute a single test file, pass the test file name as a parameter.
# All test are expected to be inside the directory <project_folder>/tests.
# Usage:
#   api-test.sh <optional_test_file>
#
# Parameters:
# <test_file>: optional

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

(cd $SCRIPT_PATH/../api/ && pip3 install -r requirements_dev.txt && PYTHONPATH=src pytest $SCRIPT_PATH/../api/tests/$1)