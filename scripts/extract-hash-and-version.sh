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

export LONG_COMMIT_HASH=$(git rev-parse HEAD)
echo "LONG_COMMIT_HASH = $LONG_COMMIT_HASH"
export SHORT_COMMIT_HASH=$(git rev-parse --short HEAD)
echo "SHORT_COMMIT_HASH = $SHORT_COMMIT_HASH"

echo "# This file is automatically created at build time. Do not delete." > $versionFile
echo "[DEFAULT]" >> $versionFile
echo "LONG_COMMIT_HASH=$LONG_COMMIT_HASH" >> $versionFile
echo "SHORT_COMMIT_HASH=$SHORT_COMMIT_HASH" >> $versionFile

# Typically actions/checkout@v4 in the workflows does not get all the tags. Get them here.
git fetch --tags

# First obtain the tags that are associated with the current commit, if any. Tags should look like this: v1.1.0.
# There could be more than one such tag. In that case take the one with the highest version.
# sort -V is great! It sorts with versions, so v10.1.1 will come after v2.1.1 for example.
export EXTRACTED_VERSION=`git tag --contains "$LONG_COMMIT_HASH" | egrep '^v[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -1`

if [ -z "$EXTRACTED_VERSION" ]; then
  # If the current commit is not tagged, get the tag from previous commits that is the closest in time, but add
  # _SNAPSHOT to it.
  EXTRACTED_VERSION=`git tag --sort=-creatordate | egrep '^v[0-9]+\.[0-9]+\.[0-9]+' | head -1`
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

echo "EXTRACTED_VERSION=$EXTRACTED_VERSION" >> $versionFile
