#!/bin/bash
#
#
#  MobilityData 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#

# Downloads a GTFS feed using the same shared code as the nightly dataset download and
# prints the request and response detail of the attempt, with credentials redacted.
# No database is required: when the config database is unreachable the download falls back
# to the default headers.

# Usage:
#   download-verifier.sh --url <producer url> [--feed_id <uuid>] [--with_upload] [--no_install_venv]
# Example:
#   download-verifier.sh --url https://example.com/gtfs.zip

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"
FUNCTION_PATH="$SCRIPT_PATH/../functions-python/batch_process_dataset"

# function printing usage
display_usage() {
  printf "\nThis script downloads a GTFS feed and prints the request and response detail"
  printf "\nScript Usage:\n"
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  -h|--help                 Display help content."
  echo "  --url <URL>               Producer URL of the feed to download. Required."
  echo "  --feed_id <UUID>          Feed UUID, to apply the per-feed http_headers config override."
  echo "  --with_upload             Also verify the upload path using the GCP storage emulator."
  echo "  --no_install_venv         Do not reinstall the python virtual environment."
  exit 1
}

url=''
feed_id=''
with_upload=false
no_install_venv=false

while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
  -h | --help)
    display_usage
    exit 0
    ;;
  --url)
    url="$2"
    shift # past argument
    shift # past value
    ;;
  --feed_id)
    feed_id="$2"
    shift # past argument
    shift # past value
    ;;
  --with_upload)
    with_upload=true
    shift # past argument
    ;;
  --no_install_venv)
    no_install_venv=true
    shift # past argument
    ;;
  *) # unknown option
    shift # past argument
    ;;
  esac
done

if [ -z "$url" ]; then
  printf "\nERROR: --url is required\n"
  display_usage
  exit 1
fi

if [ ! -d "$FUNCTION_PATH/src" ]; then
  printf "\nERROR: function's folder not found at location: %s\n" "$FUNCTION_PATH/src"
  exit 1
fi

# Link the shared code into src/shared so the function's imports resolve.
printf "\nINFO: linking shared code\n"
"$SCRIPT_PATH"/function-python-setup.sh --function_name batch_process_dataset

if [ "$no_install_venv" != "true" ]; then
  printf "\nINFO: installing python virtual environment\n"
  pushd "$FUNCTION_PATH" >/dev/null
  rm -rf venv
  pip3 install --disable-pip-version-check virtualenv >/dev/null
  python3 -m virtualenv venv >/dev/null
  venv/bin/python -m pip install --disable-pip-version-check \
    -r requirements.txt -r requirements_dev.txt >/dev/null
  popd >/dev/null
else
  printf "\nINFO: skipping python virtual environment installation\n"
fi

export PYTHONPATH="$FUNCTION_PATH/src"

args=(--url "$url")
if [ -n "$feed_id" ]; then
  args+=(--feed_id "$feed_id")
fi
if [ "$with_upload" != "true" ]; then
  args+=(--skip-upload)
fi

printf "\nINFO: downloading %s\n" "$url"
"$FUNCTION_PATH"/venv/bin/python "$FUNCTION_PATH/src/scripts/download_verifier.py" "${args[@]}"
