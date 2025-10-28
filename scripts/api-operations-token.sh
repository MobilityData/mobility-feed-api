#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   api-operations-token.sh /path/to/credentials.json [scopes] [port]
#
# Examples:
#   api-operations-token.sh ./client_secret.json \
#     "https://www.googleapis.com/auth/cloud-platform openid email profile" 8080
#   api-operations-token.sh ./client_secret.json \
#     "openid email profile" 8888
#
# Requires: jq, python3, openssl, curl
# Note: Ensure the chosen port's redirect URI (http://localhost:<port>) is listed under
#       your OAuth client’s "Authorized redirect URIs" in GCP.

CREDS_JSON="${1:-}"
SCOPES="${2:-https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile openid}"
PORT="${3:-8080}"

if [[ -z "${CREDS_JSON}" || ! -f "${CREDS_JSON}" ]]; then
  echo "Error: provide path to your Google OAuth 'web' credentials JSON." >&2
  exit 1
fi

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }; }
need jq
need python3
need openssl
need curl

CLIENT_ID="$(jq -r '.web.client_id' "${CREDS_JSON}")"
CLIENT_SECRET="$(jq -r '.web.client_secret // empty' "${CREDS_JSON}")"
AUTH_URI="$(jq -r '.web.auth_uri' "${CREDS_JSON}")"
TOKEN_URI="$(jq -r '.web.token_uri' "${CREDS_JSON}")"

if [[ -z "${CLIENT_ID}" || -z "${AUTH_URI}" || -z "${TOKEN_URI}" ]]; then
  echo "Error: client_id/auth_uri/token_uri not found under .web in ${CREDS_JSON}" >&2
  exit 1
fi

REDIRECT_URI="http://localhost:${PORT}"

# Helpers
b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }

# PKCE + state/nonce
CODE_VERIFIER="$(openssl rand -base64 64 | tr -d '\n' | tr '+/' '-_' | tr -d '=')"
CODE_CHALLENGE="$(printf '%s' "${CODE_VERIFIER}" | openssl dgst -binary -sha256 | b64url)"
STATE="$(openssl rand -hex 16)"
NONCE="$(openssl rand -hex 16)"

# Tiny one-shot HTTP server to capture ?code=
TMP_DIR="$(mktemp -d)"
CODE_FILE="${TMP_DIR}/auth_code.txt"

cat > "${TMP_DIR}/server.py" <<'PY'
import http.server, socketserver, urllib.parse, sys
PORT = int(sys.argv[1]); OUT = sys.argv[2]
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(p.query)
        code = q.get("code", [""])[0]; state = q.get("state", [""])[0]
        with open(OUT, "w") as f: f.write(code + "\n" + state + "\n")
        self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
        self.wfile.write(b"<html><body><h2>You can close this window.</h2></body></html>")
with socketserver.TCPServer(("127.0.0.1", PORT), H) as httpd: httpd.handle_request()
PY

python3 "${TMP_DIR}/server.py" "${PORT}" "${CODE_FILE}" &
SERVER_PID=$!

cleanup() {
  echo
  echo "Cleaning up local server (PID ${SERVER_PID})..."
  kill "${SERVER_PID}" >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR}" >/dev/null 2>&1 || true
}
# Clean up on normal exit, Ctrl+C (INT), termination (TERM), or error (ERR)
trap cleanup EXIT INT TERM ERR

# Build consent URL
AUTH_URL="$AUTH_URI?response_type=code&client_id=$(printf %s "${CLIENT_ID}" | jq -sRr @uri)\
&redirect_uri=$(printf %s "${REDIRECT_URI}" | jq -sRr @uri)\
&scope=$(printf %s "${SCOPES}" | jq -sRr @uri)\
&state=${STATE}&code_challenge=${CODE_CHALLENGE}&code_challenge_method=S256\
&access_type=offline&prompt=consent&nonce=${NONCE}"

# Open browser
if command -v open >/dev/null 2>&1; then
  open "${AUTH_URL}"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "${AUTH_URL}"
else
  echo "Open this URL in your browser:"
  echo "${AUTH_URL}"
fi

echo "Waiting for authorization on ${REDIRECT_URI} ..."
for _ in {1..180}; do [[ -s "${CODE_FILE}" ]] && break; sleep 1; done
if [[ ! -s "${CODE_FILE}" ]]; then
  echo "Error: no authorization code received." >&2
  exit 1
fi

AUTH_CODE="$(head -n1 "${CODE_FILE}")"
READ_STATE="$(sed -n '2p' "${CODE_FILE}")"

if [[ "${READ_STATE}" != "${STATE}" ]]; then
  echo "Error: state mismatch. Aborting." >&2
  exit 1
fi

# Exchange code for tokens
POST_DATA=(
  -d "grant_type=authorization_code"
  -d "code=${AUTH_CODE}"
  -d "redirect_uri=${REDIRECT_URI}"
  -d "client_id=${CLIENT_ID}"
  -d "code_verifier=${CODE_VERIFIER}"
)
[[ -n "${CLIENT_SECRET}" ]] && POST_DATA+=(-d "client_secret=${CLIENT_SECRET}")

TOKENS_JSON="$(curl -sS -X POST "${TOKEN_URI}" \
  -H "Content-Type: application/x-www-form-urlencoded" "${POST_DATA[@]}")"

# Parse
ACCESS_TOKEN="$(echo "${TOKENS_JSON}" | jq -r '.access_token // empty')"
EXPIRES_IN="$(echo "${TOKENS_JSON}" | jq -r '.expires_in // empty')"
REFRESH_TOKEN="$(echo "${TOKENS_JSON}" | jq -r '.refresh_token // empty')"
TOKEN_TYPE="$(echo "${TOKENS_JSON}" | jq -r '.token_type // empty')"


echo
echo "=== Token Response (trimmed) ==="
echo "${TOKENS_JSON}" | jq '{access_token, expires_in, token_type, scope, refresh_token: (has("refresh_token"))}'

echo
echo "Saved:"
echo "  ${BASE}.json            # full token response (keep secure)"
echo "  ${BASE}_access.token    # access token"
[[ -n "${REFRESH_TOKEN}" ]] && echo "  ${BASE}_refresh.token   # refresh token (store securely)"


# Exit non-zero if we failed to produce an access token
if [[ -z "${ACCESS_TOKEN}" ]]; then
  echo "ERROR: access_token is empty. Inspect ${BASE}.json for details." >&2
  exit 2
fi
