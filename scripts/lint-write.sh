#!/bin/bash

#
# Convenience script to run linters in write mode

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

cd $SCRIPT_PATH/../api/ || exit 1
pip3 install virtualenv
python -m virtualenv venv
venv/bin/python -m pip install -r requirements_dev.txt
venv/bin/python -m flake8 && venv/bin/python -m black .