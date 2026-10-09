#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Render a GTFS dataset as Parquet and publish it.

Invoked by Cloud Tasks with `{feed_stable_id, dataset_stable_id}`. Downloads the
dataset archive from the datasets bucket, converts every table, and uploads the result
to `<feed>/<dataset>/parquet/` so a browser can query it in place over range requests.

Two things about this function are deliberate and easy to undo by accident:

  * It claims the dataset in the database before doing any work, and gives up quietly
    if the claim is refused. Cloud Tasks delivers at least once, and a conversion is
    expensive enough that running it twice concurrently matters.
  * It returns HTTP 200 even when the build fails. Cloud Tasks retries non-2xx, and
    nothing here fails transiently in a way a retry would fix - a corrupt archive is
    still corrupt the second time. Failures are recorded in the tracking row, which is
    what the API reports, rather than signalled by the status code.
"""

import json
import logging
import os
import shutil
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import flask
import functions_framework
from google.cloud import storage
from sqlalchemy.orm import Session

from converter import (
    MANIFEST,
    PARQUET_CONVERTER_VERSION,
    ConvertedTable,
    SourceFacts,
    TailReader,
    convert_table,
    open_connection,
    register_table,
    table_name_for,
    write_manifest,
    zip_member_sizes_from_file,
)
from progress import (
    PHASE_CONVERT,
    PHASE_DONE,
    PHASE_START,
    PHASE_SUMMARISE,
    PHASE_UPLOAD,
    ThrottledProgress,
)
from shared.common.gcp_memory_utils import limit_gcp_memory
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset, TaskExecutionAttempt
from shared.helpers.ephemeral_workdir import EphemeralOrDebugWorkdir
from shared.helpers.logger import get_logger, init_logger
from shared.helpers.runtime_metrics import track_metrics
from shared.helpers.runtime_metrics import MemorySampler
from shared.helpers.parquet_policy import (
    DOWNSIZE_HEADROOM,
    DOWNSIZE_STREAK,
    SIZE_CONFIG_NAMESPACE,
    SIZE_TIERS,
)
from shared.helpers.sizing import (
    Basis,
    Size,
    classify_failure,
    demote,
    escalate,
    fits_within,
    function_name,
    record_size_override,
    size_override,
    tier_for,
)
from shared.helpers.task_execution.task_execution_tracker import TaskExecutionTracker
from shared.helpers.utils import create_http_parquet_builder_task

init_logger()

TASK_NAME = "parquet_generation"
BUILDER_BASE = "parquet-builder"
# Two escalations is the whole ladder: x -> m -> l. A third attempt would only repeat the
# largest worker, so the cap is the ladder's length rather than a tuning knob.
MAX_ATTEMPTS = 3
PARQUET_PREFIX = "parquet"
WORKDIR_PREFIX = "parquet_"

# Everything large goes here. It is a declared in-memory volume in deployed
# environments, so its size is already subtracted from the process budget below.
TMPDIR = os.getenv("PARQUET_TMPDIR", "/tmp/in-memory")

# DuckDB's own default reads the host's RAM rather than the cgroup, so left alone it
# spills far too late to help. Sized well under what the limiter leaves us.
DUCKDB_MEMORY_LIMIT = os.getenv("PARQUET_DUCKDB_MEMORY_LIMIT", "2GB")

# How much of an archive's tail to fetch when recovering compressed sizes. A GTFS zip
# has tens of members, so its central directory is a few kilobytes; 1 MiB is slack.
CENTRAL_DIRECTORY_TAIL = 1024 * 1024
# What the archive reader buffers per range request. Buffered in process memory, not on
# the volume, so this trades requests against RLIMIT_AS rather than against the tmpfs.
# Well under the library's 40 MiB default, which would be charged to the heap in full.
ARCHIVE_CHUNK_SIZE = 8 * 1024 * 1024

# How long a generated set lives when the caller does not say. The single source of
# truth: the API deliberately declares bounds but no default, so an omitted value
# arrives here as None rather than as someone else's idea of 30.
DEFAULT_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 60

# Must run before anything allocates: turns an overshoot into a catchable MemoryError
# instead of the kernel killing the container with no traceback and no response.
MEMORY_BUDGET = limit_gcp_memory(TMPDIR)
MIB = 1024**2


def _retention_days(value) -> int:
    """How long this set should live, defaulted and bounded.

    The API validates the range too, but this is not a duplicated check: the builder is
    reachable from Cloud Tasks and from the CLI below, neither of which goes through the
    schema, and a bad value here would otherwise be written into the tracking row and
    honoured by the sweep.
    """
    if value is None:
        return DEFAULT_RETENTION_DAYS
    try:
        days = int(value)
    except (TypeError, ValueError):
        logging.warning("Ignoring unusable retention_days %r", value)
        return DEFAULT_RETENTION_DAYS
    if days < 1 or days > MAX_RETENTION_DAYS:
        logging.warning(
            "retention_days %s is outside 1..%s; using %s",
            days,
            MAX_RETENTION_DAYS,
            DEFAULT_RETENTION_DAYS,
        )
        return DEFAULT_RETENTION_DAYS
    return days


def _budget() -> str:
    """The worker's resource budget, for the log line that reports it per build."""
    budget = MEMORY_BUDGET
    rlimit = getattr(budget, "rlimit_as_bytes", None)
    volume = getattr(budget, "volume_bytes", None)
    return (
        (
            f"{rlimit / MIB:.0f} MiB of address space"
            if rlimit
            else "no address-space limit"
        )
        + (
            f", a {volume / MIB:.0f} MiB volume at {TMPDIR}"
            if volume
            else f", an unmeasured volume at {TMPDIR}"
        )
        + f", and a DuckDB cap of {DUCKDB_MEMORY_LIMIT}"
    )


def _attempt_metadata(tables=None) -> dict:
    """What this build had to work with, beside what it used.

    An attempt that records only usage cannot answer whether that usage was comfortable,
    and reconstructing the budget afterwards from the deployment means trusting the
    deployment has not moved since. `largest_member_bytes` is the measure the routing
    table is written in, taken from the files the build actually opened rather than from
    the database columns - those columns are exactly what an override exists to correct.
    """
    budget = MEMORY_BUDGET
    sizes = [table.bytes for table in (tables or []) if table.bytes]
    return {
        "rlimit_as_bytes": getattr(budget, "rlimit_as_bytes", None),
        "volume_bytes": getattr(budget, "volume_bytes", None),
        "largest_member_bytes": max(sizes) if sizes else None,
    }


def _dataset_row(db_session, dataset_stable_id: str):
    """The dataset, for its feed. None when it cannot be read."""
    try:
        return (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.stable_id == dataset_stable_id)
            .one_or_none()
        )
    except Exception:
        return None


def _own_variant() -> Optional[Size]:
    """Which worker this is, read from the name Cloud Run gave the service.

    `K_SERVICE` is exactly what `sizing.function_name` builds - `parquet-builder-m-dev` -
    so the running size is recoverable without an env var per variant, which keeps the
    pattern free of per-function wiring.
    """
    service = os.getenv("K_SERVICE") or ""
    for size in Size:
        if service == function_name(BUILDER_BASE, size, os.getenv("ENVIRONMENT", "")):
            return size
    return None


def _escalate_after_failure(
    tracker,
    db_session,
    dataset,
    dataset_stable_id: str,
    feed_stable_id: str,
    variant: Optional[Size],
    error: BaseException,
    retention_days: int,
    logger,
) -> Optional[Size]:
    """Move the feed up a rung and re-queue, when the failure warrants it.

    Returns the size it escalated to, or None when it declined. Declining is the common
    case and has three reasons, all terminal: the failure was not a resource one, the
    build was already on the largest worker, or the attempt cap is spent. Each is a stop,
    because the alternative is a queue loop that costs money.
    """
    kind = classify_failure(error)
    if not kind.is_resource:
        return None

    attempts = tracker.attempts_since_success(dataset_stable_id)
    target = escalate(variant, SIZE_TIERS, attempts=attempts, max_attempts=MAX_ATTEMPTS)
    if target is None:
        logger.warning(
            "Not escalating %s: %s on %s after %s attempt(s)",
            dataset_stable_id,
            kind.value,
            variant.value if variant else "an unknown worker",
            attempts,
        )
        return None

    feed = getattr(dataset, "feed", None)
    if feed is None:
        logger.warning(
            "Cannot escalate %s: its feed is not resolvable", dataset_stable_id
        )
        return None

    # A lock means what it says: this build is not retried anywhere, and the dataset is
    # not produced until a person changes the value. Checked before anything is written
    # or enqueued, and reported loudly, because nothing else will raise it.
    locked = size_override(db_session, feed, SIZE_CONFIG_NAMESPACE)
    if locked.locked:
        logger.warning(
            "Not escalating %s: feed %s is locked to %s, so %s will not be retried",
            dataset_stable_id,
            feed.stable_id,
            locked.size.value if locked.size else "an unreadable size",
            kind.value,
        )
        return None

    # Only when it disagrees with the measurement: an override that merely restates the
    # measured tier pins the feed to it for good, and this dataset is already on its way
    # to `target` through the task below either way.
    record_size_override(
        db_session,
        feed,
        dataset,
        target,
        tiers=SIZE_TIERS,
        namespace=SIZE_CONFIG_NAMESPACE,
    )
    db_session.commit()
    logger.info(
        "Escalating %s from %s to %s after %s",
        dataset_stable_id,
        variant.value if variant else "unknown",
        target.value,
        kind.value,
    )
    create_http_parquet_builder_task(
        feed_stable_id,
        dataset_stable_id,
        force=True,
        retention_days=retention_days,
        size=target,
        variant_basis=Basis.AUTO.value,
        override=target.value,
    )
    return target


def _recent_attempts(db_session, feed, limit: int) -> list:
    """This feed's most recent attempts, newest first, across all of its datasets.

    Attempts are recorded against a dataset, but a size override belongs to the feed, so
    the question "has this feed been comfortable lately" spans its datasets. `run_id` is
    pinned to the converter version deliberately: a new converter is a different
    workload, and evidence gathered under the old one should not carry over.
    """
    dataset_ids = [
        row[0]
        for row in db_session.query(Gtfsdataset.stable_id)
        .filter(Gtfsdataset.feed_id == feed.id)
        .all()
    ]
    if not dataset_ids:
        return []
    return (
        db_session.query(TaskExecutionAttempt)
        .filter(
            TaskExecutionAttempt.task_name == TASK_NAME,
            TaskExecutionAttempt.run_id == PARQUET_CONVERTER_VERSION,
            TaskExecutionAttempt.entity_id.in_(dataset_ids),
        )
        .order_by(TaskExecutionAttempt.finished_at.desc())
        .limit(limit)
        .all()
    )


def _downsize_after_success(
    db_session, dataset_stable_id: str, variant: Optional[Size], logger
) -> Optional[Size]:
    """Lower this feed's override one rung when its recent builds say it can be.

    The mirror of `_escalate_after_failure`, and deliberately not its equal. Escalation
    acts on a single failure, because being too small costs a build that cannot finish.
    Being too large only costs money, so coming down waits for `DOWNSIZE_STREAK` builds
    in a row that each left `DOWNSIZE_HEADROOM` of the smaller worker unused, on both
    memory and disk.

    Nothing is re-queued. This build has already succeeded; the decision applies to the
    feed's next one.

    Every failure here is swallowed: an economy must never cost a build that worked.
    """
    try:
        if variant is None:
            return None

        target = demote(variant, SIZE_TIERS)
        if target is None:
            return None

        dataset = _dataset_row(db_session, dataset_stable_id)
        feed = getattr(dataset, "feed", None) if dataset is not None else None
        if feed is None:
            return None

        current = size_override(db_session, feed, SIZE_CONFIG_NAMESPACE)
        # No override means the feed already routes on its measurement, which is as low
        # as it goes. An override that disagrees with the worker that just ran is a state
        # this cannot reason about. A locked one is refused by `record_size_override`,
        # but returning here keeps a locked feed out of the history query entirely.
        if current.size is None or current.locked or current.size is not variant:
            return None

        tier = tier_for(target, SIZE_TIERS)
        if tier is None:
            return None

        attempts = _recent_attempts(db_session, feed, DOWNSIZE_STREAK)
        if len(attempts) < DOWNSIZE_STREAK:
            return None

        for attempt in attempts:
            metadata = attempt.metadata_ or {}
            if (
                attempt.status != "completed"
                or attempt.variant != variant.value
                or not fits_within(
                    tier,
                    peak_vms_bytes=attempt.peak_vms_bytes,
                    largest_member_bytes=metadata.get("largest_member_bytes"),
                    headroom=DOWNSIZE_HEADROOM,
                )
            ):
                return None

        record_size_override(
            db_session,
            feed,
            dataset,
            target,
            tiers=SIZE_TIERS,
            namespace=SIZE_CONFIG_NAMESPACE,
        )
        db_session.commit()
        logger.info(
            "Lowering %s from %s to %s: %s builds in a row under %.0f%% of %s",
            feed.stable_id,
            variant.value,
            target.value,
            DOWNSIZE_STREAK,
            DOWNSIZE_HEADROOM * 100,
            target.value,
        )
        return target
    except Exception:
        logger.exception("Could not review the worker size for %s", dataset_stable_id)
        db_session.rollback()
        return None


@functions_framework.http
def build_parquet_handler(request: flask.Request) -> dict:
    """Entrypoint for building the Parquet rendering of a GTFS dataset."""
    payload = request.get_json(silent=True) or {}
    feed_stable_id = payload.get("feed_stable_id")
    dataset_stable_id = payload.get("dataset_stable_id")
    force = bool(payload.get("force", False))
    retention_days = _retention_days(payload.get("retention_days"))
    # Why the Operations API routed this here. Carried for the attempt record only; the
    # worker that actually ran it comes from K_SERVICE, which cannot be wrong.
    variant_basis = payload.get("variant_basis")
    override = payload.get("override")

    if not (feed_stable_id and dataset_stable_id):
        return {
            "status": "error",
            "error": "Both feed_stable_id and dataset_stable_id must be defined.",
        }

    if not dataset_stable_id.startswith(feed_stable_id):
        return {
            "status": "error",
            "error": (
                f"feed_stable_id={feed_stable_id} is not a prefix of "
                f"dataset_stable_id={dataset_stable_id}"
            ),
        }

    bucket_name = os.getenv("DATASETS_BUCKET_NAME")
    if not bucket_name:
        return {
            "status": "error",
            "error": "DATASETS_BUCKET_NAME environment variable is not defined.",
        }

    try:
        return build_parquet(
            feed_stable_id=feed_stable_id,
            dataset_stable_id=dataset_stable_id,
            bucket_name=bucket_name,
            force=force,
            retention_days=retention_days,
            variant_basis=variant_basis,
            override=override,
        )
    except Exception as error:
        # Deliberately a 200: see the module docstring.
        logging.exception("Failed to build Parquet for dataset %s", dataset_stable_id)
        return {
            "status": "error",
            "error": f"Failed to build Parquet for dataset {dataset_stable_id}: {error}",
        }


@with_db_session
@track_metrics(metrics=("time", "memory", "cpu"))
def build_parquet(
    feed_stable_id: str,
    dataset_stable_id: str,
    bucket_name: str,
    force: bool = False,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    variant_basis: str = None,
    override: str = None,
    db_session: Session = None,
) -> dict:
    """Claim the dataset, convert it, publish it, and record what was written."""
    logger = get_logger(build_parquet.__name__, dataset_stable_id)
    started_at = datetime.now(timezone.utc)
    variant = _own_variant()
    tracker = TaskExecutionTracker(
        task_name=TASK_NAME,
        run_id=PARQUET_CONVERTER_VERSION,
        db_session=db_session,
    )
    tracker.start_run(params={"converter_version": PARQUET_CONVERTER_VERSION})

    if force:
        # Only ever moves a finished row back to claimable; it cannot take a claim away
        # from a build that is currently running.
        tracker.release_for_retry(dataset_stable_id)

    if not tracker.try_acquire(
        dataset_stable_id, execution_ref=os.getenv("K_REVISION")
    ):
        logger.info("Dataset %s is already being built elsewhere", dataset_stable_id)
        db_session.commit()
        return {
            "status": "skipped",
            "reason": "already in progress",
            "dataset": dataset_stable_id,
        }

    # Started only once the claim is held, so a request that turns out to be a duplicate
    # does not leave a sampler thread behind on a warm instance.
    sampler = MemorySampler().start()

    # `limit_gcp_memory` logs the same figures, but it runs at module import - during the
    # cold start, before any request exists - so those lines carry no trace and no
    # dataset, and pairing them with a build means joining on the instance id across
    # whatever else that instance has served since. Restating them here costs one line
    # per build and puts the budget in the same trace as the failure it explains.
    logger.info("Worker %s has %s", variant.value if variant else "unknown", _budget())

    # Committed on its own: `ThrottledProgress` swallows failures from the callback
    # below, so the claim cannot depend on the first progress write to reach the
    # database.
    db_session.commit()

    def publish(state: dict) -> None:
        # Renews the claim as well as recording the reading, so a long build holds its
        # lock by reporting rather than by a separate keepalive.
        try:
            tracker.heartbeat(dataset_stable_id, metadata=state)
            db_session.commit()
        except Exception:
            # The caller logs and carries on, so leave the session usable.
            db_session.rollback()
            raise

    progress = ThrottledProgress(publish=publish, logger=logger)
    progress.flush(phase=PHASE_START, done=0, total=0, detail="")

    try:
        with EphemeralOrDebugWorkdir(
            owner_prefix=WORKDIR_PREFIX,
            dir=TMPDIR,
            prefix=f"{dataset_stable_id}_",
        ) as workdir_name:
            workdir = Path(workdir_name)
            bucket = storage.Client().get_bucket(bucket_name)

            plan = _plan_sources(
                bucket,
                feed_stable_id,
                dataset_stable_id,
                workdir,
                progress,
                logger,
                db_session,
            )
            # One timestamp for both halves of the expiry: the objects carry it as
            # `customTime` for the bucket's lifecycle rule, and the row carries it so
            # the API can stop advertising the set on the same date.
            expires_at = datetime.now(timezone.utc) + timedelta(days=retention_days)

            tables, base_url = _convert_and_publish(
                bucket=bucket,
                feed_stable_id=feed_stable_id,
                dataset_stable_id=dataset_stable_id,
                workdir=workdir,
                plan=plan,
                progress=progress,
                logger=logger,
                expires_at=expires_at,
            )

            progress.flush(phase=PHASE_SUMMARISE, done=0, total=0, detail="")
            metadata = {
                "phase": PHASE_DONE,
                "done": len(tables),
                "total": len(tables),
                "detail": "",
                "base_url": base_url,
                "retention_days": retention_days,
                "expires_at": expires_at.isoformat(),
                "tables": [table.as_manifest_entry() for table in tables],
            }
            tracker.mark_completed(dataset_stable_id, metadata=metadata)
            tracker.record_attempt(
                dataset_stable_id,
                status="completed",
                started_at=started_at,
                variant=variant.value if variant else None,
                variant_basis=variant_basis,
                override_at_attempt=override,
                metrics=sampler.stop(),
                metadata=_attempt_metadata(tables),
            )
            db_session.commit()

            # After the commit, so this build counts towards its own streak.
            _downsize_after_success(db_session, dataset_stable_id, variant, logger)

            logger.info(
                "Built %s Parquet tables for %s", len(tables), dataset_stable_id
            )
            return {
                "status": "success",
                "dataset": dataset_stable_id,
                "base_url": base_url,
                "tables": [table.name for table in tables],
            }
    except Exception as error:
        logger.exception("Parquet build failed for %s", dataset_stable_id)
        # The failure may have come from a commit, which leaves the session refusing
        # every statement until it is rolled back - `mark_failed` included.
        db_session.rollback()
        # Releases the claim as well as recording why, so the dataset can be retried
        # without waiting out the lease.
        try:
            tracker.mark_failed(dataset_stable_id, error_message=str(error))
            db_session.commit()
        except Exception:
            logger.exception(
                "Could not record the failure for %s; the claim will expire with its "
                "lease",
                dataset_stable_id,
            )
            db_session.rollback()

        # Recording the attempt and escalating are best-effort: the build has already
        # failed, and losing the original exception to a bookkeeping error would hide
        # the thing worth reading.
        escalated_to = None
        try:
            dataset = _dataset_row(db_session, dataset_stable_id)
            escalated_to = _escalate_after_failure(
                tracker,
                db_session,
                dataset,
                dataset_stable_id,
                feed_stable_id,
                variant,
                error,
                retention_days,
                logger,
            )
            tracker.record_attempt(
                dataset_stable_id,
                status="failed",
                started_at=started_at,
                variant=variant.value if variant else None,
                variant_basis=variant_basis,
                override_at_attempt=override,
                escalated_to=escalated_to.value if escalated_to else None,
                failure_kind=classify_failure(error).value,
                error=error,
                metrics=sampler.stop(),
                metadata=_attempt_metadata(),
            )
            db_session.commit()
        except Exception:
            logger.exception("Could not record the attempt for %s", dataset_stable_id)
            db_session.rollback()
        raise


class SourcePlan:
    """Where this build's CSVs come from, resolved once up front.

    `sources` is deliberately a list of (table, fetch) rather than files on disk: the
    whole point is that only one source exists locally at a time, so materialising is
    deferred to the moment each table is converted.
    """

    def __init__(
        self,
        kind: str,
        source_bytes,
        compressed_sizes: dict,
        sources: list,
        closer=None,
    ):
        self.facts = SourceFacts(
            kind=kind, bytes=source_bytes, compressed_sizes=compressed_sizes
        )
        self.sources = sources
        # The archive plan reads members from a remote handle that has to outlive the
        # plan, so releasing it is the plan's job rather than the planner's.
        self._closer = closer

    def close(self) -> None:
        if self._closer is not None:
            self._closer()
            self._closer = None


def _plan_sources(
    bucket,
    feed_stable_id: str,
    dataset_stable_id: str,
    workdir: Path,
    progress,
    logger,
    db_session: Session,
) -> SourcePlan:
    """Prefer the files `batch_process_dataset` already extracted; fall back to the zip.

    Reading `extracted/` avoids ever holding the archive and the whole feed at once.
    The dataset's `Gtfsfile` rows are the index - they name every extracted file and
    its size without a bucket listing - and their absence is the signal that this
    dataset predates extraction (or that it failed), in which case the archive is the
    only source there is.
    """
    dataset = (
        db_session.query(Gtfsdataset)
        .filter(Gtfsdataset.stable_id == dataset_stable_id)
        .one_or_none()
    )
    files = list(dataset.gtfsfiles) if dataset else []

    if files:
        plan = _plan_from_extracted(
            bucket, feed_stable_id, dataset_stable_id, dataset, files, workdir, logger
        )
        if plan is not None:
            return plan
        # The index named files the bucket does not have. Fall through to the archive,
        # which is the authoritative copy.

    logger.info(
        "No extracted files recorded for %s; falling back to the archive",
        dataset_stable_id,
    )
    return _plan_from_archive(
        bucket, feed_stable_id, dataset_stable_id, workdir, logger
    )


def _plan_from_extracted(
    bucket, feed_stable_id, dataset_stable_id, dataset, files, workdir, logger
) -> Optional[SourcePlan]:
    """Plan from `extracted/`, or None when the bucket does not match the index.

    The `Gtfsfile` rows are an index, not a guarantee: `rebuild_missing_dataset_files`
    exists because a dataset can be recorded with files the bucket no longer holds. A
    missing object used to surface as a `NotFound` from inside the conversion, which
    lost the whole build to one absent file, so the set is checked up front instead.

    Returning None rather than converting the subset is deliberate. The manifest
    asserts it describes the dataset, so quietly dropping `feed_info` or `stop_times`
    would publish a feed that looks complete and is not.
    """
    prefix = f"{feed_stable_id}/{dataset_stable_id}/extracted"
    local_dir = workdir / "extracted"
    local_dir.mkdir(parents=True, exist_ok=True)

    # One listing rather than an existence check per file.
    present = {blob.name for blob in bucket.list_blobs(prefix=prefix + "/")}
    missing = [
        record.file_name
        for record in files
        if f"{prefix}/{record.file_name}" not in present
    ]
    if missing:
        logger.warning(
            "%s records %s extracted file(s) the bucket does not have (%s); using the "
            "archive instead. Run the rebuild_missing_dataset_files task to repair the "
            "extracted copies.",
            dataset_stable_id,
            len(missing),
            ", ".join(sorted(missing)[:5]),
        )
        return None

    sources = []
    for record in files:
        # `file_name` is the archive-relative path, so a feed wrapped in a folder is
        # recorded as "feed/stops.txt". The table is named after the basename.
        name = Path(record.file_name).name
        table = table_name_for(Path(name))
        if table is None:
            continue
        blob_path = f"{prefix}/{record.file_name}"
        sources.append(
            (table, _fetch_blob(bucket, blob_path, local_dir / name, logger))
        )

    archive_blob = bucket.blob(
        f"{feed_stable_id}/{dataset_stable_id}/{dataset_stable_id}.zip"
    )
    return SourcePlan(
        kind="zip",
        source_bytes=_archive_size(dataset, archive_blob, logger),
        compressed_sizes=_compressed_sizes_from_blob(archive_blob, logger),
        sources=sorted(sources, key=lambda item: item[0]),
    )


def _plan_from_archive(
    bucket, feed_stable_id, dataset_stable_id, workdir, logger
) -> SourcePlan:
    """Fall back to the archive, read over the network rather than downloaded.

    The archive is never written to the workdir. `Blob.open("rb")` is a seekable
    reader, which is all `zipfile` needs, so members are pulled with ranged requests as
    the converter asks for them. Downloading it instead used to cost its full size on
    the in-memory volume for the whole build, on top of the member being converted -
    for a 1 GiB archive holding a 4 GiB table, enough to exhaust the volume before
    conversion started.
    """
    blob_path = f"{feed_stable_id}/{dataset_stable_id}/{dataset_stable_id}.zip"
    archive_blob = bucket.blob(blob_path)
    if not archive_blob.exists():
        raise FileNotFoundError(
            f"Dataset archive not found at gs://{bucket.name}/{blob_path}"
        )

    archive_blob.reload()
    handle = archive_blob.open("rb", chunk_size=ARCHIVE_CHUNK_SIZE)
    try:
        zf = zipfile.ZipFile(handle)
        members = [member for member in zf.infolist() if not member.is_dir()]
    except Exception:
        handle.close()
        raise

    data_dir = workdir / "extracted"
    data_dir.mkdir(parents=True, exist_ok=True)

    sources = []
    # In archive order, not table order: a backward seek throws the reader's buffer
    # away, so converting alphabetically would refetch most of the file.
    for member in sorted(members, key=lambda m: m.header_offset):
        # Flattened: producers differ on whether the files sit at the archive root or
        # inside a folder, and the table is named after the basename either way.
        name = Path(member.filename).name
        table = table_name_for(Path(name))
        if table is None:
            continue
        sources.append((table, _extract_member(zf, member.filename, data_dir / name)))

    def close():
        zf.close()
        handle.close()

    return SourcePlan(
        kind="zip",
        # The central directory is already in hand, so the compressed sizes cost
        # nothing here - no second ranged read of the tail.
        source_bytes=int(archive_blob.size or 0),
        compressed_sizes={Path(m.filename).name: m.compress_size for m in members},
        sources=sources,
        closer=close,
    )


def _extract_member(zf: zipfile.ZipFile, member_name: str, target: Path):
    """A callable that unpacks one member when the converter is ready for it.

    Reads from the archive handle the plan holds open rather than reopening it, so a
    remote archive is not re-read per member.
    """

    def fetch() -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member_name) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
        return target

    return fetch


def _fetch_blob(bucket, blob_path: str, target: Path, logger):
    """A callable that downloads one object when the converter is ready for it."""

    def fetch() -> Path:
        blob = bucket.blob(blob_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(target))
        return target

    return fetch


def _archive_size(dataset, archive_blob, logger):
    """The archive's size, without downloading it."""
    recorded = getattr(dataset, "zipped_size_bytes", None)
    if recorded:
        return int(recorded)
    try:
        archive_blob.reload()
        return int(archive_blob.size or 0)
    except Exception as error:
        logger.warning("Could not read the archive's size: %s", error)
        return None


def _compressed_sizes_from_blob(archive_blob, logger) -> dict:
    """Per-member compressed sizes, read from the archive's tail rather than all of it.

    These exist only in the zip's central directory, so reading `extracted/` would
    otherwise lose them and the load report's Zipped column would be blank for every
    dataset built this way. The directory sits at the end of the file, so a ranged read
    of the last megabyte is enough.
    """
    try:
        archive_blob.reload()
        size = int(archive_blob.size or 0)
        if not size:
            return {}
        start = max(0, size - CENTRAL_DIRECTORY_TAIL)
        tail = archive_blob.download_as_bytes(start=start, end=size - 1)
        return zip_member_sizes_from_file(TailReader(tail, size))
    except Exception as error:
        logger.warning("Could not read compressed sizes from the archive: %s", error)
        return {}


def _convert_and_publish(
    bucket,
    feed_stable_id,
    dataset_stable_id,
    workdir,
    plan,
    progress,
    logger,
    expires_at,
):
    """Convert and publish one table at a time, holding no more than one of each.

    Each table is fetched, converted, uploaded and deleted before the next begins, so
    peak memory tracks the largest single table rather than the whole feed. The
    manifest still goes up last - it is what tells a reader the set is complete.
    """
    dest_prefix = f"{feed_stable_id}/{dataset_stable_id}/{PARQUET_PREFIX}"
    existing = {blob.name for blob in bucket.list_blobs(prefix=dest_prefix + "/")}
    written = set()

    out_dir = workdir / PARQUET_PREFIX
    out_dir.mkdir(parents=True, exist_ok=True)
    con = open_connection(temp_dir=workdir / "duckdb", memory_limit=DUCKDB_MEMORY_LIMIT)
    tables: list[ConvertedTable] = []
    try:
        total = len(plan.sources)
        for index, (table, fetch) in enumerate(plan.sources, start=1):
            progress(PHASE_CONVERT, index, total, table)
            source = fetch()
            try:
                if not register_table(con, table, source, logger):
                    continue
                entry = convert_table(
                    con,
                    table,
                    source,
                    out_dir,
                    plan.facts.compressed_sizes.get(source.name),
                )
            finally:
                source.unlink(missing_ok=True)

            parquet = out_dir / entry.file
            written.add(_publish(bucket, dest_prefix, parquet, logger, expires_at))
            parquet.unlink(missing_ok=True)
            tables.append(entry)
    finally:
        con.close()
        plan.close()

    # Converted in archive order for the reader's sake; reported by name so the manifest
    # does not depend on which path produced it.
    tables.sort(key=lambda entry: entry.name)

    if not tables:
        raise ValueError(f"No GTFS tables could be converted for {dataset_stable_id}")

    progress.flush(phase=PHASE_CONVERT, done=len(tables), total=len(tables))

    progress(PHASE_UPLOAD, 1, 1, MANIFEST)
    manifest = write_manifest(out_dir, tables, plan.facts)
    written.add(_publish(bucket, dest_prefix, manifest, logger, expires_at))
    manifest.unlink(missing_ok=True)
    progress.flush(phase=PHASE_UPLOAD, done=1, total=1, detail=MANIFEST)

    for name in sorted(existing - written):
        bucket.blob(name).delete()
        logger.info("Removed stale object %s", name)

    public_base = os.getenv("PUBLIC_HOSTED_DATASETS_URL", "").rstrip("/")
    return tables, f"{public_base}/{dest_prefix}"


def _uniform_access(bucket) -> bool:
    """True when the bucket grants access by policy, so per-object ACLs do not apply."""
    try:
        return bool(bucket.iam_configuration.uniform_bucket_level_access_enabled)
    except Exception:
        return False


def _publish(bucket, dest_prefix: str, path: Path, logger, expires_at) -> str:
    blob = bucket.blob(f"{dest_prefix}/{path.name}")
    # The date the bucket's lifecycle rule deletes this object. Set on the upload, so
    # it costs no extra request; GCS ignores it until a rule names customTime.
    blob.custom_time = expires_at
    blob.upload_from_filename(str(path))
    try:
        blob.make_public()
    except Exception as error:
        # Only harmless under uniform bucket-level access, where ACLs do not apply and
        # the objects are public by policy. Elsewhere the file is published but
        # unreadable, and the build would report `ready` on a base_url that 403s.
        if not _uniform_access(bucket):
            raise
        logger.debug(
            "Skipping ACL on %s: bucket uses uniform access (%s)", blob.name, error
        )
    return blob.name


def main():  # pragma: no cover
    if len(sys.argv) < 2:
        print("Usage: python src/main.py <dataset_stable_id>")
        sys.exit(1)

    dataset_stable_id = sys.argv[1]
    feed_stable_id = dataset_stable_id.rsplit("-", 1)[0]
    payload = {"feed_stable_id": feed_stable_id, "dataset_stable_id": dataset_stable_id}

    with flask.Flask(__name__).test_request_context(json=payload):
        print(json.dumps(build_parquet_handler(flask.request), indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
