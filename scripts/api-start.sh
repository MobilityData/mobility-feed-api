#!/bin/bash

# This script starts the uvicorn process listening in port 8080.

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"
PORT=8080
(cd $SCRIPT_PATH/../api/src && uvicorn main:app --host 0.0.0.0 --port $PORT --env-file ../../config/.env.local)