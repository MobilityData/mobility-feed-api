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
import sys
import tempfile
from pathlib import Path

import flask
import functions_framework
from google.cloud import storage
from sqlalchemy.orm import Session

from converter import PARQUET_CONVERTER_VERSION, convert_to_parquet, extract_feed
from progress import (
    PHASE_CONVERT,
    PHASE_DONE,
    PHASE_DOWNLOAD,
    PHASE_EXTRACT,
    PHASE_START,
    PHASE_SUMMARISE,
    PHASE_UPLOAD,
    ThrottledProgress,
)
from shared.database.database import with_db_session
from shared.helpers.logger import get_logger, init_logger
from shared.helpers.runtime_metrics import track_metrics
from shared.helpers.task_execution.task_execution_tracker import TaskExecutionTracker

init_logger()

TASK_NAME = "parquet_generation"
PARQUET_PREFIX = "parquet"


@functions_framework.http
def build_parquet_handler(request: flask.Request) -> dict:
    """Entrypoint for building the Parquet rendering of a GTFS dataset."""
    payload = request.get_json(silent=True) or {}
    feed_stable_id = payload.get("feed_stable_id")
    dataset_stable_id = payload.get("dataset_stable_id")
    force = bool(payload.get("force", False))

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
    db_session: Session = None,
) -> dict:
    """Claim the dataset, convert it, publish it, and record what was written."""
    logger = get_logger(build_parquet.__name__, dataset_stable_id)
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

    def publish(state: dict) -> None:
        # Renews the claim as well as recording the reading, so a long build holds its
        # lock by reporting rather than by a separate keepalive.
        tracker.heartbeat(dataset_stable_id, metadata=state)
        db_session.commit()

    progress = ThrottledProgress(publish=publish, logger=logger)
    progress.flush(phase=PHASE_START, done=0, total=0, detail="")

    try:
        with tempfile.TemporaryDirectory(
            prefix=f"{dataset_stable_id}-"
        ) as workdir_name:
            workdir = Path(workdir_name)
            bucket = storage.Client().get_bucket(bucket_name)

            archive = _download_archive(
                bucket, feed_stable_id, dataset_stable_id, workdir, progress, logger
            )
            data_dir = _extract(archive, workdir, progress, logger)

            out_dir = workdir / PARQUET_PREFIX
            tables = convert_to_parquet(
                data_dir=data_dir,
                destination=out_dir,
                on_progress=progress,
                logger=logger,
            )
            progress.flush(phase=PHASE_CONVERT, done=len(tables), total=len(tables))

            base_url = _upload(
                bucket, feed_stable_id, dataset_stable_id, out_dir, progress, logger
            )

            progress.flush(phase=PHASE_SUMMARISE, done=0, total=0, detail="")
            manifest = {
                "phase": PHASE_DONE,
                "done": len(tables),
                "total": len(tables),
                "detail": "",
                "base_url": base_url,
                "tables": [table.as_manifest_entry() for table in tables],
            }
            tracker.mark_completed(dataset_stable_id, metadata=manifest)
            db_session.commit()

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
        # Releases the claim as well as recording why, so the dataset can be retried
        # without waiting out the lease.
        tracker.mark_failed(dataset_stable_id, error_message=str(error))
        db_session.commit()
        raise


def _download_archive(
    bucket, feed_stable_id, dataset_stable_id, workdir, progress, logger
) -> Path:
    """Fetch the dataset archive, reporting bytes as it goes."""
    blob_path = f"{feed_stable_id}/{dataset_stable_id}/{dataset_stable_id}.zip"
    blob = bucket.blob(blob_path)
    if not blob.exists():
        raise FileNotFoundError(
            f"Dataset archive not found at gs://{bucket.name}/{blob_path}"
        )

    blob.reload()
    # `download` counts bytes, not files, which is what the viewer's wording expects
    # for this phase. 0 when the size is unknown, as a missing Content-Length would be.
    total = int(blob.size or 0)
    progress(PHASE_DOWNLOAD, 0, total, f"{dataset_stable_id}.zip")

    archive = workdir / f"{dataset_stable_id}.zip"
    blob.download_to_filename(str(archive))
    progress.flush(
        phase=PHASE_DOWNLOAD,
        done=archive.stat().st_size,
        total=total,
        detail=f"{dataset_stable_id}.zip",
    )
    logger.info("Downloaded gs://%s/%s", bucket.name, blob_path)
    return archive


def _extract(archive: Path, workdir: Path, progress, logger) -> Path:
    """Unpack the archive, reporting one event per member."""
    data_dir = extract_feed(archive, workdir / "extracted", on_progress=progress)
    count = len(list(data_dir.iterdir()))
    progress.flush(phase=PHASE_EXTRACT, done=count, total=count)
    logger.info("Extracted %s files", count)
    return data_dir


def _upload(
    bucket, feed_stable_id, dataset_stable_id, out_dir: Path, progress, logger
) -> str:
    """Publish the Parquet set, replacing whatever was there before."""
    dest_prefix = f"{feed_stable_id}/{dataset_stable_id}/{PARQUET_PREFIX}"

    # Cleared first so a rebuild that produces fewer tables cannot leave a stale one
    # behind for a reader to find.
    for stale in bucket.list_blobs(prefix=dest_prefix + "/"):
        stale.delete()

    files = sorted(out_dir.iterdir())
    for index, path in enumerate(files, start=1):
        progress(PHASE_UPLOAD, index, len(files), path.name)
        blob = bucket.blob(f"{dest_prefix}/{path.name}")
        blob.upload_from_filename(str(path))
        try:
            blob.make_public()
        except Exception as error:
            # Uniform bucket-level access would make this unnecessary and impossible at
            # the same time; the objects are public by bucket policy in that case.
            logger.warning("Could not make %s public: %s", blob.name, error)
    progress.flush(phase=PHASE_UPLOAD, done=len(files), total=len(files))

    public_base = os.getenv("PUBLIC_HOSTED_DATASETS_URL", "").rstrip("/")
    logger.info("Uploaded %s files to gs://%s/%s", len(files), bucket.name, dest_prefix)
    return f"{public_base}/{dest_prefix}"


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
