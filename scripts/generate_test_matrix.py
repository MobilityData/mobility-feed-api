#!/usr/bin/env python3
"""
Generate the GitHub Actions test matrix for the Build and Test workflow.

Auto-discovers every runnable target (a functions-python/<name> directory with a
tests/ dir and a requirements.txt, plus the fixed "api" target) — no target is ever
named here, so a new function picked up under functions-python/ needs no workflow
change to be tested.

Some targets have grown a large enough test suite that running the whole thing as one
pytest session, in one process, on one GitHub-hosted runner, reliably exhausts the
runner's memory partway through and takes the test DB down with it (see the
tasks_executor incident this was written for). To avoid that without hand-maintaining
a list of "which subfolders go in which CI job", this script also auto-shards: for any
target whose test count exceeds TARGET_TESTS_PER_SHARD, it discovers every directory
(at any depth) under that target's tests/ that directly contains test_*.py files,
weighs each by its number of `def test_` functions, and greedily bin-packs them
(largest first, always onto the currently lightest shard) into balanced groups. A new
test subdirectory added anywhere later is picked up the same way on the next run — no
workflow change needed there either.

Each matrix entry carries:
  folder      - the target's directory, e.g. "functions-python/tasks_executor"
  group       - unique per shard, e.g. "tasks_executor-shard-1"; used for artifact names
  function    - shared by every shard of the same target, e.g. "tasks_executor"; used by
                the coverage-gate job to recombine shards before checking the threshold
  test_paths  - space-separated paths (relative to folder) to pass to pytest instead of
                the bare "tests" directory. Always "tests" for an unsharded target.

Writes `matrix=<json>` to $GITHUB_OUTPUT. Run from the repository root.
"""

import json
import math
import os
import re

TARGET_TESTS_PER_SHARD = 250

TEST_DEF_RE = re.compile(r"^\s*def test_", re.MULTILINE)

# Directories that never hold real tests of their own: caches, venvs, and the
# gitignored symlinks that function-python-setup.sh creates (shared code, test_shared).
EXCLUDED_DIRNAMES = {"__pycache__", "venv", ".venv", "test_shared"}


def count_tests_in_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return len(TEST_DEF_RE.findall(f.read()))
    except OSError:
        return 0


def discover_buckets(tests_root):
    """Return {relative_bucket_dir: weight} for every directory (at any depth) under
    tests_root that directly contains at least one test_*.py file. A directory's
    weight only counts test_*.py files directly inside it — a subdirectory with its
    own test files is always its own separate bucket, never double-counted here.
    """
    buckets = {}
    for dirpath, dirnames, filenames in os.walk(tests_root):
        dirnames[:] = [
            d for d in dirnames if d not in EXCLUDED_DIRNAMES and not d.endswith("_gen")
        ]
        test_files = [f for f in filenames if f.startswith("test_") and f.endswith(".py")]
        if not test_files:
            continue
        weight = sum(count_tests_in_file(os.path.join(dirpath, f)) for f in test_files)
        if weight == 0:
            continue
        buckets[os.path.relpath(dirpath, tests_root)] = weight
    return buckets


def shard_target(name, folder):
    """Return the matrix entries for one target, sharded only if it needs to be."""
    buckets = discover_buckets(os.path.join(folder, "tests"))
    total = sum(buckets.values())
    num_shards = max(1, math.ceil(total / TARGET_TESTS_PER_SHARD)) if total else 1

    if num_shards == 1:
        # Either small enough to run as one job, or nothing was discoverable (in which
        # case running "tests" as-is surfaces that loudly instead of silently vanishing).
        return [{"folder": folder, "group": name, "function": name, "test_paths": "tests"}]

    # Greedy LPT (Longest Processing Time first) bin-packing: not optimal in general,
    # but simple, deterministic, and plenty balanced for this many buckets/shards.
    shard_paths = [[] for _ in range(num_shards)]
    shard_weights = [0] * num_shards
    for rel, weight in sorted(buckets.items(), key=lambda kv: kv[1], reverse=True):
        i = shard_weights.index(min(shard_weights))
        shard_paths[i].append(rel)
        shard_weights[i] += weight

    entries = []
    for i, paths in enumerate(shard_paths, start=1):
        test_paths = " ".join(
            "tests" if p == "." else os.path.join("tests", p) for p in sorted(paths)
        )
        entries.append(
            {
                "folder": folder,
                "group": f"{name}-shard-{i}",
                "function": name,
                "test_paths": test_paths,
            }
        )
    return entries


def discover_targets():
    """Yield (name, folder) for every runnable target, "api" first."""
    yield "api", "api"
    for entry in sorted(os.listdir("functions-python")):
        folder = os.path.join("functions-python", entry)
        if not os.path.isdir(os.path.join(folder, "tests")):
            continue
        if not os.path.isfile(os.path.join(folder, "requirements.txt")):
            continue
        yield entry, folder


def main():
    matrix_entries = []
    for name, folder in discover_targets():
        matrix_entries += shard_target(name, folder)

    matrix_json = json.dumps({"include": matrix_entries})
    print(f"Generated {len(matrix_entries)} matrix entries:")
    print(json.dumps(matrix_entries, indent=2))

    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"matrix={matrix_json}\n")


if __name__ == "__main__":
    main()
