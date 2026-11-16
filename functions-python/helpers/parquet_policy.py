#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Which worker a Parquet build belongs on.

Two processes decide this and they have to agree. The Operations API routes a build when
it enqueues one, and the builder re-routes it when one runs out of resources; if their
tables disagreed, a dataset would bounce between two workers forever. They used to hold
separate copies with a comment in each saying they must match, which is a comment where
a shared constant belongs.

`sizing.py` is the mechanism and is deliberately generic. This is the Parquet builder's
policy: its bands, its budgets, its config key, and the thresholds that move a feed
between rungs.
"""

from __future__ import annotations

from shared.helpers.sizing import Size, Tier

MIB = 1024**2

# Routing table for the build workers. The measure is the largest single uncompressed
# file in the dataset, because the builder's in-memory volume holds one at a time, so
# that file is what decides whether a build fits. Totals are the wrong signal: a feed of
# many medium files is cheaper than one with a single huge one, and the compressed size
# is wrong by a factor that runs from 4x to 13x across the catalogue.
#
# The bands come from measuring it: of 4277 feeds, the median archive is 0.2 MB and only
# 31 are above 100 MB, while about ten feeds have a single member over 1 GB and the worst
# has one of 4.8 GB. So most traffic belongs on a worker sized for a few hundred MB, and
# the large worker exists for roughly a dozen feeds. Stats as of 2026/09.
#
# `vms_budget_bytes` is the other half: what the rung provides, beside what it accepts.
# Each is the RLIMIT_AS the worker ends up with, which `limit_gcp_memory` derives as
# memory - volume - 200 MiB margin, from `local.parquet_builder_sizes` in
# infra/functions-python/main.tf. A build records what it actually used, so these are
# what that usage gets compared against when deciding a feed could run somewhere smaller.
# Change them when the terraform map changes; a worker logs its real RLIMIT_AS at
# startup, so a drift is visible rather than silent.
SIZE_TIERS = (
    # 3Gi memory, 1Gi volume
    Tier(size=Size.S, max_bytes=256_000_000, vms_budget_bytes=1848 * MIB),
    # 7Gi memory, 3Gi volume
    Tier(size=Size.M, max_bytes=1_500_000_000, vms_budget_bytes=3896 * MIB),
    # 16Gi memory, 8Gi volume
    Tier(size=Size.L, max_bytes=None, vms_budget_bytes=7992 * MIB),
)

# A feed can be pinned to a size by hand through `config_value_feed`. An override is used
# as given; the measurement is not consulted at all.
SIZE_CONFIG_NAMESPACE = "parquet_builder"
SIZE_CONFIG_KEY = "size"

# Used only when a dataset has no per-file rows and no recorded unzipped total. GTFS
# compresses roughly 5-15x; the low end is deliberate, since overestimating the content
# of an archive routes up rather than down.
COMPRESSION_RATIO = 5

# How many consecutive successful builds a feed needs before its override comes down a
# rung, and how much of the smaller rung each of them has to leave unused.
#
# The two directions are deliberately asymmetric. Escalation acts on a single failure,
# because the cost of staying too small is a build that cannot finish. Coming down is
# only ever an economy, so it can afford to be slow and dull: three builds in a row, each
# leaving 40% of the smaller worker spare on both memory and disk.
#
# Both are dials. A feed whose datasets alternate between large and small is the case
# that could still move down and back up repeatedly - the disk axis usually catches it,
# because the large dataset's own build breaks the streak, but that is a property of the
# evidence rather than a guarantee. If flapping shows up in `task_execution_attempt`,
# lengthen the streak or lower the fraction.
DOWNSIZE_STREAK = 3
DOWNSIZE_HEADROOM = 0.60
