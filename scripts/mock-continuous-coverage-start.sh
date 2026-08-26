#!/bin/bash

# This script serves the continuous coverage panel mock at http://localhost:8095.
#
# The page opens on a captured API response, so it needs nothing else running. To point it at a
# live feed instead, start the API with scripts/api-start.sh and use the form at the top of the page.

set -e

SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"
PORT="${PORT:-8095}"
MOCK_DIR="$SCRIPT_PATH/../docs/mocks/continuous-coverage"

echo "Serving the continuous coverage mock on http://localhost:$PORT"
echo "Press Ctrl+C to stop."

(cd "$MOCK_DIR" && python3 -m http.server "$PORT" --bind 127.0.0.1)
