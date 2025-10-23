#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/api-operations-update-schema.sh \
#     [--source ./docs/DatabaseCatalogAPI.yaml] \
#     [--dest ./docs/OperationsAPI.yaml]
#
# Behavior:
# - Replaces components.schemas in Operations with those from Catalog.
# - Preserves only schemas in Operations that have x-operation: true at the schema root (these override source).
# - Removes any non-operation schemas that exist only in Operations.

SCRIPT_DIR="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SOURCE=""
DEST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source|-s) SOURCE="${2:-}"; shift 2 ;;
    --dest|-d) DEST="${2:-}"; shift 2 ;;
    -h|--help) echo "Usage: $0 [--source <CatalogYAML>] [--dest <OperationsYAML>]"; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

: "${SOURCE:=${REPO_ROOT}/docs/DatabaseCatalogAPI.yaml}"
: "${DEST:=${REPO_ROOT}/docs/OperationsAPI.yaml}"

if ! command -v yq >/dev/null 2>&1; then
  echo "yq not found. Install with: brew install yq" >&2
  exit 1
fi
YQ_MAJOR="$(yq --version 2>/dev/null | sed -n 's/.*version v\([0-9][0-9]*\).*/\1/p')"
if [[ -z "${YQ_MAJOR:-}" || "${YQ_MAJOR}" -lt 4 ]]; then
  echo "yq v4+ required. Current: $(yq --version 2>/dev/null)" >&2
  exit 1
fi

[[ -f "${SOURCE}" ]] || { echo "Source not found: ${SOURCE}" >&2; exit 1; }
[[ -f "${DEST}" ]]   || { echo "Dest not found: ${DEST}"   >&2; exit 1; }

cp -f "${DEST}" "${DEST}.bak"

# Merge strategy:
# - Start from source schemas (Catalog): ensures Operations aligns with source by default
# - Overlay ONLY the destination schemas that are explicitly marked with x-operation: true
#   (these are preserved and override the source)
# - Any non-operation schemas that exist only in Operations are DROPPED
SRC_ABS="$(cd "$(dirname "${SOURCE}")" && pwd)/$(basename "${SOURCE}")"
export SRC="${SRC_ABS}"

yq -i '
  (.components.schemas // {}) as $dst
  | (load(strenv(SRC)).components.schemas // {}) as $src
  | .components.schemas = (
      $src
      * (
          $dst
          | with_entries( select(.value."x-operation" == true) )
        )
    )
' "${DEST}"

echo "Synced schemas from ${SOURCE} -> ${DEST} (${DEST}.bak created)."
echo "Note: Schemas in Operations with x-operation: true were preserved."