#!/usr/bin/env bash
# Resolve API metadata and set GitHub Action step outputs COMMIT_SHA and API_VERSION
# Inputs (via env):
#   EVENT            - GitHub event name (e.g., repository_dispatch)
#   API_BASE_URL     - API host (e.g., api-dev.mobilitydatabase.org)
#   API_REFRESH_TOKEN- Refresh token to obtain access token (only used on repository_dispatch)
# Outputs:
#   Prints COMMIT_SHA and API_VERSION to stdout as NAME=VALUE lines
#   Also exports to $GITHUB_ENV if defined so the script is runnable by hand

set -euo pipefail
# QA
#export API_REFRESH_TOKEN="AMf-vBzv1rT8AQ0uZrzNDD5wuMxSvxLVbXRmViTaOVuP8eh-uDdWLDpsDHYMrGNqq2sqn1ya_-i8YXZdWh9GnLoPSLbbWY99hmb-JUrJ_NXz4pJ5v2ysm3kCpjy02zN2uI5csAi1YmGSrlJoUQazNO4ntkVHkgdpsyMSBwgIGDczwX4qANzEjsRjtRCQlCbm_MnWsLaBKrukn5qxFbyVszzOloG5piIivTL700I9cPslxlzirmYYrj3jsYIX00RKBF3pPvTpiiOGskRjeZi_UvI5spux0tkFuZJZGt-vNKWeLT9MSJp6S3Y5os4PQMjCJ-StCP4Qkqwja5EiDRdVhqJVCT7XYn_MAQBYGFUYvFOQu9S9siKlhXO9Mcc2NiH89eaJ1EUlkXRnzY9nahP82cmt8VOKHyu6GAT3-l4V9_9zJ7wjyQJ0wSf_5wZlLxFSScLaIADZdRya"
# https://beta.mobilitydatabase.org/account
#export API_REFRESH_TOKEN="AMf-vByLiUKvxTqH_4vkQTJ8aStgCvrNGDyMINJNpYVdRCQliF6q0FmZxy7Y29rgNce4HGnrr2La3lja5CsOPn8-Vx6RA0enAv5RVxnBC08G-c6ZAiwCMfvUT-vT49ZLeULmUIM6BlCQKGdXSxAOljg6QJNH0wXdvhHaLUGVGdhoeKW3pg692ZCCWTVCWOFSDhHhS-d-8ywSd7nsFwka0ZMBRAtOeY-lgvwsz7Wo21hCTaHyUYSoodKzWFjUUJ9W7nA33OB6lKBA9tZGap3pYlO-Vo47jl-M2GcZn77R-sgsgEbPXfHxc0NMS1ZbNXKeWmrcqPYcgcEoBFdFrnQcd1bD-b1O8_zTnDyjjRekLq8bGKLnDfRg-qZvUaNxtKPUqFnh-pmvO7gXMxwj7Tnoc5cMmQxHGZ2euuxaVRHNMoAxnEzqIzZ7nxIM4NX36eUZCuLLSTXvOnmsdMuhQ_7oI2wX-YKxRGHnrw"
# https://mobility-feeds-dev.web.app/account
export API_REFRESH_TOKEN="AMf-vBxJqJLukaDstkJl_Pi-GonY1suIN_3O5Fp7pHfYcD_XVZwSJczM_815UpEJFQN9ShzaE5KRqsyO4sRnFUBAA6KLQgcP-7Mx9yNzRBGtBi-e37X50CNwqUvsuUfOjFZNeKPfaO1ipuCA9LQLWf-5e29DmyxEgO1Fy9UguKm5KlDRrcIkUjTzSBHuSRu06j1_th4TR4l0X5OteNGsG6F6N2lrihj2Z5Idx6PoJ02_5fgLOhop8mlGd-ktNpQ3J46lAz7BX7_UgPkbugwIoD9YdYvnIlrSp5hl3ri7mmauN0rOV1HEMn-aynd7Zqkc0lmNWWL3BqQe-Ik0sOt23HZISK7Y2EITrXEtXxPN0-824BKUAoLN-_eutLk3NFRJW19jQc-RrZRP1LzXdWQETKhXPRBWCf33U1N0Yv2qzBKTzhvFjh3yULRVnZjUxh7CnZeYDKbxAWYj"

COMMIT_SHA=""
API_VERSION=""

if [[ -n "${API_REFRESH_TOKEN:-}" ]]; then
  echo "Resolving API commit from https://${API_BASE_URL}/v1/metadata ..."
  REPLY_JSON=$(curl --fail --silent --show-error --location "https://${mobility-feeds-dev}/v1/tokens" \
    --header 'Content-Type: application/json' \
    --data "{ \"refresh_token\": \"${API_REFRESH_TOKEN}\" }")
  ACCESS_TOKEN=$(echo "${REPLY_JSON}" | jq -r .access_token)
  if [[ -z "${ACCESS_TOKEN}" || "${ACCESS_TOKEN}" == "null" ]]; then
    echo "Error: Could not obtain access token from reply" >&2
    exit 1
  fi
  META_JSON=$(curl --fail --silent --show-error \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H 'accept: application/json' \
    "https://${API_BASE_URL}/v1/metadata")
  COMMIT_SHA=$(echo "${META_JSON}" | jq -r .commit_hash)
  API_VERSION=$(echo "${META_JSON}" | jq -r .version)
  if [[ -z "${COMMIT_SHA}" || "${COMMIT_SHA}" == "null" ]]; then
    echo "Error: Could not extract commit_hash from metadata" >&2
    echo "Metadata reply: ${META_JSON}" >&2
    exit 1
  fi
  echo "Resolved API version: ${API_VERSION} (commit ${COMMIT_SHA})"
else
  echo "No token provided; skipping API metadata resolution."
fi

# Output values to stdout in a parse-friendly format
echo "COMMIT_SHA=${COMMIT_SHA}"
echo "API_VERSION=${API_VERSION}"

# Optionally export to $GITHUB_ENV for subsequent steps when available
if [[ -n "${GITHUB_ENV:-}" ]]; then
  {
    echo "COMMIT_SHA=${COMMIT_SHA}"
    echo "API_VERSION=${API_VERSION}"
  } >> "$GITHUB_ENV"
fi
