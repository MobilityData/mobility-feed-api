#!/usr/bin/env python3
#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

import pandas as pd
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Feed, Redirectingid

logger = logging.getLogger(__name__)

CAL_ITP_REDIRECT_DATA_LINK = (
    "https://raw.githubusercontent.com/MobilityData/mobility-feed-api/"
    "refs/heads/main/functions-data/cal_itp_feed_redirect/redirect_mdb_to_cal_itp.csv"
)

DEFAULT_COMMIT_BATCH_SIZE = 100

def _update_feed_redirect(
    db_session: Session, mdb_stable_id: str, cal_itp_stable_id: str
) -> Dict[str, int]:
    """
    Ensure there is a Redirectingid from MDB feed to Cal-ITP feed.

    Returns a dict with counters:
      {
        "redirects_created": 0|1,
        "redirects_existing": 0|1,
        "missing_mdb_feeds": 0|1,
        "missing_cal_itp_feeds": 0|1,
      }
    """
    counters = {
        "redirects_created": 0,
        "redirects_existing": 0,
        "missing_mdb_feeds": 0,
        "missing_cal_itp_feeds": 0,
    }

    mdb_feed: Feed | None = (
        db_session.query(Feed).filter(Feed.stable_id == mdb_stable_id).one_or_none()
    )
    if not mdb_feed:
        logger.warning(
            "MDB feed not found for stable_id=%s, skipping redirect", mdb_stable_id
        )
        counters["missing_mdb_feeds"] = 1
        return counters

    cal_itp_feed: Feed | None = (
        db_session.query(Feed).filter(Feed.stable_id == cal_itp_stable_id).one_or_none()
    )
    if not cal_itp_feed:
        logger.warning(
            "Cal-ITP feed not found for stable_id=%s, skipping redirect", cal_itp_stable_id
        )
        counters["missing_cal_itp_feeds"] = 1
        return counters

    # Both feeds exist: ensure redirect exists (source MDB → target Cal-ITP).
    redirect = (
        db_session.query(Redirectingid)
        .filter(
            Redirectingid.target_id == cal_itp_feed.id,
            Redirectingid.source_id == mdb_feed.id,
        )
        .one_or_none()
    )

    if redirect:
        logger.info(
            "Redirect already exists: source=%s → target=%s",
            mdb_stable_id,
            cal_itp_stable_id,
        )
        counters["redirects_existing"] = 1
        return counters

    logger.info(
        "Creating redirect: source=%s → target=%s",
        mdb_stable_id,
        cal_itp_stable_id,
    )
    redirect = Redirectingid(
        target_id=cal_itp_feed.id,
        source_id=mdb_feed.id,
        redirect_comment="Redirecting post Cal-ITP import",
    )
    mdb_feed.status = "deprecated"
    db_session.add(redirect)
    counters["redirects_created"] = 1
    return counters


def commit_changes(db_session: Session, created_since_commit: int) -> None:
    """
    ACID Commit DB changes for redirects.
    """
    try:
        logger.info(
            "Committing DB changes after creating %d redirect(s)", created_since_commit
        )
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
        logger.exception(
            "Commit failed with IntegrityError; rolled back Cal-ITP redirects batch"
        )


@with_db_session
def _update_cal_itp_redirects(db_session: Session, dry_run: bool = True) -> dict:
    """
    Orchestrate Cal-ITP redirect updates:
      - Load redirect CSV
      - For each row, ensure redirect from MDB → Cal-ITP
      - Support dry_run and batch commits (COMMIT_BATCH_SIZE)
    """
    logger.info("Starting Cal-ITP redirects update dry_run=%s", dry_run)

    try:
        df = pd.read_csv(CAL_ITP_REDIRECT_DATA_LINK)
    except Exception as e:
        logger.exception(
            "Failed to load Cal-ITP redirect CSV from %s", CAL_ITP_REDIRECT_DATA_LINK
        )
        return {
            "message": "Failed to load Cal-ITP redirect CSV.",
            "error": str(e),
            "params": {"dry_run": dry_run},
            "rows_processed": 0,
            "redirects_created": 0,
            "redirects_existing": 0,
            "missing_mdb_feeds": 0,
            "missing_cal_itp_feeds": 0,
        }

    commit_batch_size = int(
        os.getenv("COMMIT_BATCH_SIZE", str(DEFAULT_COMMIT_BATCH_SIZE))
    )
    logger.info("Commit batch size (env COMMIT_BATCH_SIZE)=%s", commit_batch_size)

    rows_processed = 0
    redirects_created = 0
    redirects_existing = 0
    missing_mdb_feeds = 0
    missing_cal_itp_feeds = 0

    created_since_commit = 0

    for idx, row in df.iterrows():
        mdb_stable_id = row.get("MDB ID")
        cal_itp_ids_raw = row.get("Cal-ITP ID")

        if not isinstance(mdb_stable_id, str) or not isinstance(cal_itp_ids_raw, str):
            logger.warning(
                "Skipping row index=%s: invalid MDB/Cal-ITP IDs row=%s",
                idx,
                row.to_dict(),
            )
            continue

        cal_itp_stable_ids = [
            f"cal_itp-{stable_id.strip()}"
            for stable_id in cal_itp_ids_raw.split(",")
            if str(stable_id).strip()
        ]

        for cal_itp_stable_id in cal_itp_stable_ids:
            rows_processed += 1
            logger.debug(
                "Processing redirect row: MDB=%s Cal-ITP=%s",
                mdb_stable_id,
                cal_itp_stable_id,
            )

            counters = _update_feed_redirect(
                db_session=db_session,
                mdb_stable_id=mdb_stable_id,
                cal_itp_stable_id=cal_itp_stable_id,
            )

            redirects_created += counters["redirects_created"]
            redirects_existing += counters["redirects_existing"]
            missing_mdb_feeds += counters["missing_mdb_feeds"]
            missing_cal_itp_feeds += counters["missing_cal_itp_feeds"]

            created_since_commit += counters["redirects_created"]

            if not dry_run and created_since_commit >= commit_batch_size:
                commit_changes(db_session, created_since_commit)
                created_since_commit = 0

    if not dry_run and created_since_commit > 0:
        commit_changes(db_session, created_since_commit)

    message = (
        "Dry run: no DB writes performed."
        if dry_run
        else "Cal-ITP redirects update executed successfully."
    )
    summary = {
        "message": message,
        "rows_processed": rows_processed,
        "redirects_created": redirects_created,
        "redirects_existing": redirects_existing,
        "missing_mdb_feeds": missing_mdb_feeds,
        "missing_cal_itp_feeds": missing_cal_itp_feeds,
        "params": {"dry_run": dry_run},
    }
    logger.info("Cal-ITP redirects update summary: %s", summary)
    return summary


def update_cal_itp_redirects_handler(payload: Optional[dict] = None) -> dict:
    """
    Cloud Function-style entrypoint.

    Payload: {"dry_run": bool} (default True)
    """
    payload = payload or {}
    logger.info("update_cal_itp_redirects_handler called with payload=%s", payload)

    dry_run_raw = payload.get("dry_run", True)
    dry_run = (
        dry_run_raw
        if isinstance(dry_run_raw, bool)
        else str(dry_run_raw).lower() == "true"
    )
    logger.info("Parsed dry_run=%s (raw=%s)", dry_run, dry_run_raw)

    result = _update_cal_itp_redirects(dry_run=dry_run)
    logger.info(
        "update_cal_itp_redirects_handler summary: %s",
        {
            k: result.get(k)
            for k in (
                "message",
                "rows_processed",
                "redirects_created",
                "redirects_existing",
                "missing_mdb_feeds",
                "missing_cal_itp_feeds",
            )
        },
    )
    return result
