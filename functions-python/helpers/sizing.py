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
"""Routing a job to a worker sized for it.

A function provisioned for its worst case spends most of its life running trivial work.
Measured on `pmtiles-builder-prod`, 85% of invocations finish inside 30 seconds and
account for under 7% of the compute, while every one of them is billed at the memory the
largest feed needs. Deploying the same source as two differently sized functions and
choosing between them at enqueue time is what this module exists for.

It is deliberately generic: the caller supplies the tiers and the measure, so
`pmtiles_builder` and `reverse_geolocation` can adopt it without copying the logic.

Two rules:

- **An unknown measure routes to the largest tier.** Sizes come from database columns
  that are nullable and were added without a backfill, so "I don't know" is a normal
  answer, and guessing small turns a missing row into an OOM.
- **An override decides on its own.** A configured size is the answer, whichever way it
  differs from the measurement. The measurement is a heuristic; someone who set the
  config has looked at the feed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Sequence


class Size(Enum):
    """Worker sizes, ordered smallest first. `value` is the routing suffix."""

    M = "m"
    L = "l"

    @property
    def rank(self) -> int:
        return _RANK[self]

    def __lt__(self, other: "Size") -> bool:
        return self.rank < other.rank

    @classmethod
    def parse(cls, raw) -> Optional["Size"]:
        """A size from free-form config, or None when it is absent or unrecognised.

        Config values are operator-entered, so an unusable one must not be fatal - it
        falls back to the measured size rather than failing the request.
        """
        if raw is None:
            return None
        try:
            return cls(str(raw).strip().lower())
        except ValueError:
            logging.warning("Ignoring unrecognised size override %r", raw)
            return None


_RANK = {Size.M: 0, Size.L: 1}

LARGEST = Size.L


@dataclass(frozen=True)
class Tier:
    """One row of a routing table: this size, for measures below this many bytes."""

    size: Size
    max_bytes: Optional[int]  # None is the catch-all and must come last


def choose_size(
    measure: Optional[int],
    tiers: Sequence[Tier],
    override: Optional[Size] = None,
) -> Size:
    """Pick a worker size for a job whose weight is `measure` bytes.

    An `override` is returned as given and the measurement is not consulted.

    `measure` is whatever bounds the job - for a Parquet build, the largest single
    uncompressed file, because the volume holds one at a time. `None` means unknown,
    which routes to the largest tier.
    """
    if override is not None:
        return override

    if measure is None:
        return LARGEST

    for tier in tiers:
        if tier.max_bytes is None or measure < tier.max_bytes:
            return tier.size
    return LARGEST


def first_known(*candidates: Optional[int]) -> Optional[int]:
    """The first candidate that is a usable positive size, or None.

    Size columns are nullable and can be zero for a dataset whose files were never
    recorded, so a plain `or` chain would let a 0 through as a real measurement and
    route the job to the smallest worker.
    """
    for candidate in candidates:
        if candidate:
            try:
                value = int(candidate)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
    return None


def queue_env_var(prefix: str, size: Size) -> str:
    """The env var naming the Cloud Tasks queue for this size, e.g. `..._QUEUE_L`."""
    return f"{prefix}_QUEUE_{size.value.upper()}"


def function_name(base: str, size: Size, environment: str) -> str:
    """The deployed function name for this size, e.g. `parquet-builder-l-dev`."""
    return f"{base}-{size.value}-{environment}"


def describe(tiers: Iterable[Tier]) -> str:
    """A routing table in one line, for the log that records why a size was chosen."""
    return ", ".join(
        (
            f"{tier.size.value}<{tier.max_bytes}"
            if tier.max_bytes
            else f"{tier.size.value}:rest"
        )
        for tier in tiers
    )
