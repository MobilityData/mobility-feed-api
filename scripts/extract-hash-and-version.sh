#!/bin/bash

#
# This script uses git to extract the commit hash that is being used and the version based on the the git tags.
#
export LONG_COMMIT_HASH=$(git rev-parse HEAD)
echo "$LONG_COMMIT_HASH" > api/src/commit_hash
export SHORT_COMMIT_HASH=$(git rev-parse --short HEAD)
echo "LONG_COMMIT_HASH = $LONG_COMMIT_HASH"
echo "SHORT_COMMIT_HASH = $SHORT_COMMIT_HASH"


# Typically the tags are not fetched with actions/checkout@v4.
# Instead of forcing all callers to get the tags, get them here.
# The ls-remote will return all the tags and their commit hash. A typical line from thi call looks like:
#    a09cc2548eaaa17c21e41eac7226a030846be97a	refs/tags/v4.8.1
# We are interested only in the tags associated with the commit hash already extracted.
# There could be more than one such tag.
commitTags=$(git ls-remote --tags origin | grep -F "$LONG_COMMIT_HASH" | awk '{sub("refs/tags/", "", $2); print $2}')

# Then accept only tags with vX.X.X pattern.
# sort -V is great! It sorts with versions, so v10.1.1 will come after v2.1.1 for example.
# The last one after that should be the latest version.
EXTRACTED_VERSION=$(echo "$commitTags" | egrep '^v[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -1)
if [ -z "$EXTRACTED_VERSION" ]; then
   EXTRACTED_VERSION="0.0.0"
fi
echo "$EXTRACTED_VERSION" > api/src/version
export EXTRACTED_VERSION
echo "EXTRACTED_VERSION = $EXTRACTED_VERSION"

versionFile=api/src/version_info
echo "# This file is automatically created a build time. Do not delete." > $versionFile
echo "[DEFAULT]" >> $versionFile
echo "LONG_COMMIT_HASH=$LONG_COMMIT_HASH" >> $versionFile
echo "SHORT_COMMIT_HASH=$SHORT_COMMIT_HASH" >> $versionFile
echo "EXTRACTED_VERSION=$EXTRACTED_VERSION" >> $versionFile
