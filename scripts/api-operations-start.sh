#!/bin/bash

# This script starts the uvicorn process for the Operations API listening on port 8081.

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"
PORT=8081
(cd $SCRIPT_PATH/../functions-python/operations_api/src && uvicorn main:app --host 0.0.0.0 --port $PORT --env-file ../../../config/.env.local)
