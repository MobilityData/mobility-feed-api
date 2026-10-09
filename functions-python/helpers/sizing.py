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

The tier arithmetic is generic: the caller supplies the tiers and the measure.
`size_for_dataset` builds on it for the common case of a job whose weight is a GTFS
dataset, which is how every candidate function here is triggered.

Whether the *measure* transfers is a separate question per function. The largest single
uncompressed file is right for the Parquet builder because its volume holds one at a
time; a function bounded by something else wants `choose_size` with its own measure.

Two rules:

- **An unknown measure routes to the largest tier.** Sizes come from database columns
  that are nullable and were added without a backfill, so "I don't know" is a normal
  answer, and guessing small turns a missing row into an OOM.
- **An override decides on its own.** A configured size is the answer, whichever way it
  differs from the measurement. The measurement is a heuristic; someone who set the
  config has looked at the feed.
"""

from __future__ import annotations

import errno
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Iterable, Optional, Sequence

from sqlalchemy import func

from shared.common.config_reader import get_config_value
from shared.database_gen.sqlacodegen_models import Gtfsfile

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm import Session

# GTFS compresses roughly 5-15x. The low end is deliberate: overestimating what an
# archive expands to routes a job up a rung rather than down.
DEFAULT_COMPRESSION_RATIO = 5


class Basis(Enum):
    """Where a size came from, recorded so a change is legible afterwards."""

    MEASURED = "measured"
    OPERATOR = "operator"
    AUTO = "auto"


class FailureKind(Enum):
    """What ran out, when something did."""

    RESOURCE_MEMORY = "resource_memory"
    RESOURCE_DISK = "resource_disk"
    OTHER = "other"

    @property
    def is_resource(self) -> bool:
        return self is not FailureKind.OTHER


# Matched on the exception's class name rather than by importing the libraries that raise
# them, so this stays usable from any function without pulling in duckdb.
_MEMORY_TYPES = {"MemoryError", "OutOfMemoryException"}
_DISK_MARKERS = ("no space left on device", "errno 28")


def classify_failure(exc: BaseException) -> FailureKind:
    """What kind of exhaustion this failure was, if any.

    Reads the exception, not a stored message, because `str(MemoryError())` is the empty
    string - CPython raises a no-args singleton - so the failure the largest worker
    exists for is invisible once the message has been written to a column.
    """
    name = type(exc).__name__
    message = str(exc).lower()

    if isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.ENOSPC:
        return FailureKind.RESOURCE_DISK
    # DuckDB reports a full spill directory as its own IOException, not an OSError.
    if any(marker in message for marker in _DISK_MARKERS):
        return FailureKind.RESOURCE_DISK
    if name in _MEMORY_TYPES or message.startswith("out of memory error"):
        return FailureKind.RESOURCE_MEMORY
    return FailureKind.OTHER


class Size(Enum):
    """Worker sizes, smallest first. `value` is the routing suffix."""

    S = "s"
    M = "m"
    L = "l"

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


def escalate(
    current: Optional[Size],
    tiers: Sequence[Tier],
    *,
    attempts: int,
    max_attempts: int,
) -> Optional[Size]:
    """The next rung up for a job that ran out of resources, or None to stop.

    None means stop, for any of three reasons: the attempt cap is spent, the job is
    already on the largest rung, or the current rung is unknown. All three are terminal,
    because the alternative is a loop that re-queues forever at real cost.
    """
    if attempts >= max_attempts:
        return None

    ladder = [tier.size for tier in tiers]
    if current is None or current not in ladder:
        return None

    index = ladder.index(current)
    if index + 1 >= len(ladder):
        return None
    return ladder[index + 1]


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


def largest_file_bytes(db_session: "Session", dataset) -> Optional[int]:
    """The biggest single uncompressed file in the dataset, or None if unrecorded.

    One indexed aggregate on `gtfsfile`, which carries an index on `gtfs_dataset_id`.
    Returns None rather than 0 for a dataset with no file rows, so the caller can tell
    "no files recorded" from "files recorded, all empty".
    """
    try:
        return (
            db_session.query(func.max(Gtfsfile.file_size_bytes))
            .filter(Gtfsfile.gtfs_dataset_id == dataset.id)
            .scalar()
        )
    except Exception as error:
        logging.warning("Could not measure %s: %s", dataset.stable_id, error)
        return None


def measure_dataset(
    db_session: "Session",
    dataset,
    compression_ratio: int = DEFAULT_COMPRESSION_RATIO,
) -> tuple[Optional[int], str]:
    """How heavy a dataset is, and which rung of the fallback produced the answer.

    The size columns are nullable and were added without a backfill, so a dataset
    processed before #1284 has none of them. Each rung is a worse approximation than the
    one above, and all of them err upwards: `unzipped_size_bytes` is the sum rather than
    the maximum, and the compressed estimate uses the low end of the ratio.
    """
    largest = largest_file_bytes(db_session, dataset)
    if largest:
        return int(largest), "largest file"

    total = first_known(getattr(dataset, "unzipped_size_bytes", None))
    if total:
        return total, "unzipped total"

    zipped = first_known(getattr(dataset, "zipped_size_bytes", None))
    if zipped:
        return zipped * compression_ratio, "estimated from the archive"

    return None, "unknown"


# Marks a value the builder wrote for itself. Anything without it was set by a person.
SOURCE_AUTO = "auto"
SOURCE_OPERATOR = "operator"


def size_override(
    db_session: "Session", feed, namespace: str, key: str = "size"
) -> tuple[Optional[Size], Optional[str]]:
    """The size configured for this feed and who set it, or `(None, None)`.

    One row per feed holds both cases, because what differs between them is the author,
    not the value:

    - a bare `"l"` is a person's, and decides outright;
    - `{"size": "l", "source": "auto"}` is the builder's own, and only raises a measured
      size.

    The bare form is what a human writing SQL by hand produces, so it is the one that
    needs no ceremony.
    """
    try:
        raw = get_config_value(namespace, key, feed_id=feed.id, db_session=db_session)
    except Exception as error:
        logging.warning(
            "Could not read the size override for %s: %s", feed.stable_id, error
        )
        return None, None

    if isinstance(raw, dict):
        return Size.parse(raw.get("size")), raw.get("source") or SOURCE_AUTO
    size = Size.parse(raw)
    return size, SOURCE_OPERATOR if size else None


@dataclass(frozen=True)
class Routing:
    """A sizing decision: what to run on, and where that came from."""

    size: Size
    basis: Basis


def size_for_dataset(
    db_session: "Session",
    feed,
    dataset,
    *,
    tiers: Sequence[Tier],
    namespace: str,
    key: str = "size",
    compression_ratio: int = DEFAULT_COMPRESSION_RATIO,
) -> Routing:
    """Which worker should handle this dataset, and where that came from.

    An override decides; otherwise the measurement picks a tier. Nothing else.

    The override is absolute whoever wrote it. A person's is obvious enough. The
    builder's own is absolute too, because the alternative - weighing it against the
    measurement so a grown feed can overtake it - only changes the outcome when the
    measurement is larger, and that case already resolves itself: the build fails and the
    escalation moves it up. One wasted build is not worth a second code path.

    `source` is carried for the record, not to change the decision.
    """
    override, source = size_override(db_session, feed, namespace, key)
    if override is not None:
        basis = Basis.AUTO if source == SOURCE_AUTO else Basis.OPERATOR
        logging.info(
            "Routing %s to %s: %s override on feed %s",
            dataset.stable_id,
            override.value,
            basis.value,
            feed.stable_id,
        )
        return Routing(size=override, basis=basis)

    measure, how = measure_dataset(db_session, dataset, compression_ratio)
    size = choose_size(measure, tiers)

    if measure is None:
        logging.warning(
            "No recorded size for %s (%s); routing to %s. Run the "
            "rebuild_missing_dataset_files task to record them.",
            dataset.stable_id,
            how,
            size.value,
        )
    else:
        logging.info(
            "Routing %s to %s: %s bytes by %s, table [%s]",
            dataset.stable_id,
            size.value,
            measure,
            how,
            describe(tiers),
        )
    return Routing(size=size, basis=Basis.MEASURED)


def set_size_override(
    db_session: "Session", feed, size: Size, namespace: str, key: str = "size"
) -> None:
    """Record the size this feed should use from now on, so the next run starts there.

    Written as an object so the row says the builder set it rather than a person. Both
    forms decide outright; the source is kept for the record.

    Written to `config_value_feed`, which has no foreign key to `feed` and requires both
    `feed_id` and a NOT NULL `feed_stable_id`, so both are supplied. `updated_at` has a
    server default on insert only and is set explicitly on the update path.
    """
    from sqlalchemy.dialects.postgresql import insert

    from shared.database_gen.sqlacodegen_models import ConfigValueFeed

    now = datetime.now(timezone.utc)
    value = {"size": size.value, "source": SOURCE_AUTO}
    statement = (
        insert(ConfigValueFeed)
        .values(
            feed_id=feed.id,
            feed_stable_id=feed.stable_id,
            namespace=namespace,
            key=key,
            value=value,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["feed_id", "namespace", "key"],
            set_={"value": value, "updated_at": now},
        )
    )
    db_session.execute(statement)
    logging.info(
        "Feed %s now requires at least the %s worker", feed.stable_id, size.value
    )
