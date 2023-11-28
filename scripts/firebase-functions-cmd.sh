#!/bin/bash

# First argument is the task (i.e. test, lint)
TASK=$1

find functions -name 'package.json' -not -path '*/node_modules/*' -exec dirname {} \; | while read dir; do
    echo "Running $TASK in $dir"
    (cd "$dir" && yarn "$TASK")
done