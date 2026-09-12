#!/bin/bash
#
# gtfs-to-parquet.sh
#
# Converts a GTFS ZIP file into Parquet files for efficient browser-side
# pagination and search via DuckDB-WASM + HTTP Range requests.
#
# Usage:
#   scripts/gtfs-to-parquet.sh --feed-id <MDB_ID> [--env dev|qa|prod] [--upload]
#   scripts/gtfs-to-parquet.sh --url <GTFS_URL> [--upload] [--env dev|qa|prod]
#   scripts/gtfs-to-parquet.sh --file <LOCAL_ZIP> [--output <DIR>]
#
# Options (passed through to gtfs_to_parquet.py):
#   --feed-id ID           MobilityDatabase feed ID (e.g. mdb-2014). Downloads from
#                          files.mobilitydatabase.org/{id}/latest.zip automatically.
#   --url URL              Direct URL of the GTFS ZIP to download
#   --file FILE            Path to a local GTFS ZIP file
#   --env dev|qa|prod      Target GCS environment for upload (default: dev)
#   --upload               Upload generated Parquet files to GCS after conversion
#   --dataset-id ID        Override the dataset ID for the GCS upload path
#   --output DIR           Local output directory (default: ./gtfs_parquet_output)
#   --row-group-size N     Rows per Parquet row group (default: 50000)
#   --no-sort              Skip sorting for faster ingestion
#
# Examples:
#   # Convert latest mdb-2014 and upload to dev(Only intended for internal team it requires MobilityData permissions):
#   ./scripts/gtfs-to-parquet.sh --feed-id mdb-2014 --upload --env dev
#
#   # Convert and upload to prod(Only intended for internal team it requires MobilityData permissions):
#   ./scripts/gtfs-to-parquet.sh --feed-id mdb-2014 --upload --env prod
#
#   # Convert from direct URL, keep local only:
#   ./scripts/gtfs-to-parquet.sh --url "https://files.mobilitydatabase.org/mdb-10/latest.zip"
#
#   # Convert local file:
#   ./scripts/gtfs-to-parquet.sh --file ~/Downloads/gtfs.zip --output /tmp/gtfs_out
#
# After running locally, serve for the POC viewer:
#   python3 scripts/gtfs_parquet_serve.py --dir ./gtfs_parquet_output
#

set -euo pipefail

# Resolve script directory (works with symlinks and relative paths)
SCRIPT_PATH="$(
  cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd -P
)"
REPO_ROOT="$SCRIPT_PATH/.."
VENV_DIR="$SCRIPT_PATH/.venv-gtfs-parquet"
PYTHON_SCRIPT="$SCRIPT_PATH/gtfs_to_parquet.py"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

display_usage() {
  # Print the leading comment block, skipping shebang; stop at first code line
  awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} /^$/{next} {exit}' "$0"
  exit 0
}

# Show help if requested or no arguments
if [[ $# -eq 0 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
  display_usage
fi

printf "${CYAN}[gtfs-to-parquet]${NC} Setting up Python environment...\n"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
  pip3 install --disable-pip-version-check virtualenv >/dev/null 2>&1
  python3 -m virtualenv "$VENV_DIR" >/dev/null 2>&1
  printf "${GREEN}[OK]${NC} Created virtualenv at %s\n" "$VENV_DIR"
fi

# Install / upgrade dependencies silently
"$VENV_DIR/bin/pip" install --disable-pip-version-check --quiet --upgrade \
  "duckdb>=0.10" \
  "requests>=2.28" 2>/dev/null

printf "${GREEN}[OK]${NC} Dependencies ready\n"
printf "${CYAN}[gtfs-to-parquet]${NC} Running conversion...\n\n"

# Run the Python script, passing all arguments through
"$VENV_DIR/bin/python" "$PYTHON_SCRIPT" "$@"
