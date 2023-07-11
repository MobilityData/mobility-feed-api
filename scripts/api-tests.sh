#!/bin/bash

# relative
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

(cd $SCRIPT_PATH/../api/ && pip3 install -r requirements_dev.txt && PYTHONPATH=src pytest $SCRIPT_PATH/../api/tests/$1)