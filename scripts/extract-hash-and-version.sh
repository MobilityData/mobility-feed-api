#!/bin/bash
#
# This script uses git to extract the commit hash that is being used and the version based on the the git tags.
#
set -e

versionFile=api/src/version_info

handle_error() {
    echo "An error occurred. $versionFile might not have been properly filled."
    exit 1
}
trap 'handle_error' ERR

LONG_COMMIT_HASH=$(git rev-parse HEAD)
echo "LONG_COMMIT_HASH = $LONG_COMMIT_HASH"
SHORT_COMMIT_HASH=$(git rev-parse --short HEAD)
echo "SHORT_COMMIT_HASH = $SHORT_COMMIT_HASH"

echo "# This file is automatically created at build time. Do not delete." > $versionFile
echo "[DEFAULT]" >> $versionFile
echo "LONG_COMMIT_HASH=$LONG_COMMIT_HASH" >> $versionFile
echo "SHORT_COMMIT_HASH=$SHORT_COMMIT_HASH" >> $versionFile

# First obtain the tags that are associated with the current commit, if any. Tags should look like this: v1.1.0
# sort -V is great! It sorts with versions, so v10.1.1 will come after v2.1.1 for example.
EXTRACTED_VERSION=`git tag --contains "$LONG_COMMIT_HASH" | egrep '^v[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -1`

if [ -z "$EXTRACTED_VERSION" ]; then
  # If there are no tags on the current commit, get all the tags with the latest at the end of the list.
  # Typically actions/checkout@v4 in the workflows does not get the all tags. Get them ince we have to dig into past tags,
  # tet them here
  git fetch --tags
  EXTRACTED_VERSION=`git tag --sort=-creatordate | egrep '^v[0-9]+\.[0-9]+\.[0-9]+' | head -1`
  if [ -z "$EXTRACTED_VERSION" ]; then
    EXTRACTED_VERSION="v0.0.0"
  else
    # Since the tag is on an earlier commit, use the latest tag and add SNAPSHOT
    EXTRACTED_VERSION+="_SNAPSHOT"
  fi
fi
echo "EXTRACTED_VERSION = $EXTRACTED_VERSION"

echo "EXTRACTED_VERSION=$EXTRACTED_VERSION" >> $versionFile
