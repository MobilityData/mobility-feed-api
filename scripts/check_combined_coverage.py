#!/usr/bin/env python3
"""
Combine every shard's coverage data back into one report per target and enforce the
branch-coverage threshold once, holistically.

See generate_test_matrix.py for why targets get sharded into several CI matrix jobs in
the first place: --skip_coverage_gate there means no individual shard ever fails on
coverage alone, since a shard only ever exercises part of a target's source tree. This
script is what actually enforces the threshold, per target, after every shard's data
has been downloaded.

Expects:
  - MATRIX_JSON env var: the same matrix JSON generate_test_matrix.py produced
    ({"include": [{folder, group, function, test_paths}, ...]}).
  - Each shard's raw coverage data already downloaded to
    <COVERAGE_DOWNLOAD_DIR>/coverage_data_<group>/coverage.dat (i.e.
    actions/download-artifact with pattern: coverage_data_*, merge-multiple: false —
    that "one subdirectory per artifact" layout is what keeps every shard's identically
    -named coverage.dat from clobbering its siblings).

Exits non-zero if any target's combined branch coverage is under COVERAGE_THRESHOLD.
"""

import json
import os
import subprocess
import sys

COVERAGE_THRESHOLD = 80
DOWNLOAD_DIR = os.environ.get("COVERAGE_DOWNLOAD_DIR", "coverage_data")


def targets_from_matrix(matrix_json):
    """{function: {folder, groups: [group, ...]}} from the matrix's flat entry list."""
    targets = {}
    for entry in json.loads(matrix_json)["include"]:
        target = targets.setdefault(entry["function"], {"folder": entry["folder"], "groups": []})
        target["groups"].append(entry["group"])
    return targets


def combine_and_check(function, folder, groups):
    data_files = []
    for group in groups:
        path = os.path.abspath(os.path.join(DOWNLOAD_DIR, f"coverage_data_{group}", "coverage.dat"))
        if not os.path.isfile(path):
            print(f"::warning::{function}: missing coverage data for shard {group} ({path})")
            continue
        data_files.append(path)

    if not data_files:
        print(f"::error::{function}: no coverage data found for any shard")
        return False

    combined_file = ".coverage.combined"
    env = {**os.environ, "COVERAGE_FILE": combined_file}

    subprocess.run(
        ["python3", "-m", "coverage", "combine", "--keep", *data_files],
        cwd=folder,
        env=env,
        check=True,
    )
    report = subprocess.run(
        ["python3", "-m", "coverage", "report"],
        cwd=folder,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    print(f"\n=== {function}: combined coverage across {len(data_files)} shard(s) ===")
    print(report.stdout)

    total_line = next(line for line in report.stdout.splitlines() if line.startswith("TOTAL"))
    percentage = int(total_line.split()[-1].rstrip("%"))
    passed = percentage >= COVERAGE_THRESHOLD
    verdict = "OK" if passed else "BELOW THRESHOLD"
    print(f"{function}: {percentage}% branch coverage ({verdict}, threshold {COVERAGE_THRESHOLD}%)")
    return passed


def main():
    subprocess.run(
        ["python3", "-m", "pip", "install", "--disable-pip-version-check", "-q", "coverage"],
        check=True,
    )

    targets = targets_from_matrix(os.environ["MATRIX_JSON"])
    failures = [
        function
        for function, info in sorted(targets.items())
        if not combine_and_check(function, info["folder"], info["groups"])
    ]

    if failures:
        print(f"\n::error::Combined branch coverage below {COVERAGE_THRESHOLD}% for: {', '.join(failures)}")
        sys.exit(1)
    print(f"\nCombined branch coverage is above or equal to {COVERAGE_THRESHOLD}% for every target.")


if __name__ == "__main__":
    main()
