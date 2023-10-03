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

cd $SCRIPT_PATH/../api/ || exit 1
pip3 install --user virtualenv
python -m virtualenv venv
venv/bin/python -m pip install -r requirements_dev.txt
venv/bin/python -m flake8 && venv/bin/python -m black . --check