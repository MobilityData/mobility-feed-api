#!/bin/bash
#
# This script uses git to extract the commit hash that is being used and the version based on the git tags.
#
set -e

version_file=api/src/version_info

handle_error() {
    echo "An error occurred. $version_file might not have been properly filled."
    exit 1
}
trap 'handle_error' ERR

# Default environment
env=""

# Parse arguments
while getopts ":e:" opt; do
  case $opt in
    e)
      env=$OPTARG
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      exit 1
      ;;
  esac
done

get_latest_commit_in_main() {
    git fetch origin main
    git rev-parse origin/main
}

get_latest_release_tag() {
    git fetch --tags
    # Get the latest tag that is not a SNAPSHOT or a release candidate
    git tag --sort=-creatordate | egrep '^v[0-9]+\.[0-9]+\.[0-9]+' | egrep -v 'SNAPSHOT|rc' | head -1
}

if [ -n "$env" ]; then
  if [ "$env" == "qa" ]; then
    LONG_COMMIT_HASH=$(get_latest_commit_in_main)
  elif [ "$env" == "prod" ]; then
    latest_tag=$(get_latest_release_tag)
    LONG_COMMIT_HASH=$(git rev-list -n 1 $latest_tag)
  else
    LONG_COMMIT_HASH=$(git rev-parse HEAD) # Default to the current commit
  fi
else
  LONG_COMMIT_HASH=$(git rev-parse HEAD)
fi

echo "LONG_COMMIT_HASH = $LONG_COMMIT_HASH"
SHORT_COMMIT_HASH=$(git rev-parse --short $LONG_COMMIT_HASH)
echo "SHORT_COMMIT_HASH = $SHORT_COMMIT_HASH"

echo "# This file is automatically created at build time. Do not delete." > $version_file
echo "[DEFAULT]" >> $version_file
echo "LONG_COMMIT_HASH=$LONG_COMMIT_HASH" >> $version_file
echo "SHORT_COMMIT_HASH=$SHORT_COMMIT_HASH" >> $version_file

# Typically actions/checkout@v4 in the workflows does not get all the tags. Get them here.
git fetch --tags

# First obtain the tags that are associated with the current commit, if any. Tags should look like this: v1.1.0.
# There could be more than one such tag. In that case take the one with the highest version.
# sort -V is great! It sorts with versions, so v10.1.1 will come after v2.1.1 for example.
EXTRACTED_VERSION=$(git tag --contains "$LONG_COMMIT_HASH" | egrep '^v[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -1)

if [ -z "$EXTRACTED_VERSION" ]; then
  # If the current commit is not tagged, get the tag from previous commits that is the closest in time, but add
  # _SNAPSHOT to it.
  EXTRACTED_VERSION=$(git tag --sort=-creatordate | egrep '^v[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  if [ -z "$EXTRACTED_VERSION" ]; then
    EXTRACTED_VERSION="v0.0.0"
  else
    EXTRACTED_VERSION+="_SNAPSHOT"
  fi
fi
echo "EXTRACTED_VERSION = $EXTRACTED_VERSION"

# We want this script to be runnable by hand. In that case GITHUB_ENV is not defined
if [ ! -z "$GITHUB_ENV" ]; then
  echo "EXTRACTED_VERSION=$EXTRACTED_VERSION" >> $GITHUB_ENV
fi

echo "EXTRACTED_VERSION=$EXTRACTED_VERSION" >> $version_file
