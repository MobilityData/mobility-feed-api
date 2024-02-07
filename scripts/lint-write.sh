#!/bin/bash

#
# This script write lint rules based on flake8.
# Usage:
#   lint-write.sh

# absolute path
ABS_SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

# funtion to execute tests with parameter path
execute_lint() {
    printf "\nExecuting lint write in $1\n" 
    cd $ABS_SCRIPTPATH/$1 || exit 1
    pip3 install --disable-pip-version-check virtualenv > /dev/null
    python -m virtualenv venv > /dev/null
    venv/bin/python -m pip install -r requirements_dev.txt > /dev/null
    venv/bin/python -m flake8 && venv/bin/python -m black .
    if [ $? -ne 0 ]; then
        printf "\nError running lint\n"
        exit 1
    fi
    printf "\n"
}

execute_lint "../api/"
execute_lint "../functions-python/"
execute_lint "../integration-tests/"

