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
import uuid
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List, Final, TypeVar

import pycountry
import requests
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.common.locations_utils import create_or_get_location
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Feedrelatedlink,
    Externalid,
)
from shared.helpers.pub_sub import trigger_dataset_download
from tasks.data_import.data_import_utils import (
    get_or_create_entity_type,
    get_or_create_feed,
)

T = TypeVar("T", bound="Feed")

logger = logging.getLogger(__name__)

JBDA_BASE: Final[str] = "https://api.gtfs-data.jp/v2"
FEEDS_URL: Final[str] = f"{JBDA_BASE}/feeds"
DETAIL_URL_TMPL: Final[str] = f"{JBDA_BASE}/organizations/{{org_id}}/feeds/{{feed_id}}"
REQUEST_TIMEOUT_S: Final[int] = 60

URLS_TO_ENTITY_TYPES_MAP: Final[dict[str, str]] = {
    "trip_update_url": "tu",
    "vehicle_position_url": "vp",
    "alert_url": "sa",
}

RID_DESCRIPTIONS: Final[dict[str, str]] = {
    "next_1": "The URL for a future feed version with an upcoming service period.",
    "next_2": "The URL for a future feed version with a service period that will proceed after next_1.",
    "prev_1": "The URL for the expired feed version. This URL was proceeded by the current feed.",
    "prev_2": "The URL for a past feed version with an expired service period.",
}


def import_jbda_handler(payload: dict | None = None) -> dict:
    """
    Cloud Function entrypoint.
    Payload: {"dry_run": bool} (default True)
    """
    payload = payload or {}
    logger.info("import_jbda_handler called with payload=%s", payload)

    dry_run_raw = payload.get("dry_run", True)
    dry_run = (
        dry_run_raw
        if isinstance(dry_run_raw, bool)
        else str(dry_run_raw).lower() == "true"
    )
    logger.info("Parsed dry_run=%s (raw=%s)", dry_run, dry_run_raw)

    result = _import_jbda(dry_run=dry_run)
    logger.info(
        "import_jbda_handler summary: %s",
        {
            k: result.get(k)
            for k in (
                "message",
                "created_gtfs",
                "updated_gtfs",
                "created_rt",
                "linked_refs",
                "total_processed_items",
            )
        },
    )
    return result


def get_gtfs_file_url(
    detail_body: Dict[str, Any], rid: str = "current"
) -> Optional[str]:
    """
    Build & validate the GTFS file download URL for a given rid (e.g., 'current', 'next_1', 'prev_1').
    Uses a HEAD request (fast) and returns None for 404 or failures.
    """
    org_id = detail_body.get("organization_id")
    feed_id = detail_body.get("feed_id")
    if not org_id or not feed_id:
        logger.warning(
            "Cannot construct GTFS file URL; missing organization_id (%s) or feed_id (%s)",
            org_id,
            feed_id,
        )
        return None

    expected_url = f"https://api.gtfs-data.jp/v2/organizations/{org_id}/feeds/{feed_id}/files/feed.zip?rid={rid}"
    try:
        resp = requests.head(expected_url, allow_redirects=True, timeout=15)
        if resp.status_code == 200:
            logger.debug("Verified GTFS file URL (rid=%s): %s", rid, expected_url)
            return expected_url
        logger.debug(
            "GTFS file URL check failed for rid=%s (status=%s)", rid, resp.status_code
        )
    except requests.RequestException as e:
        logger.warning("HEAD request failed for %s: %s", expected_url, e)
    return None


def _update_common_feed_fields(
    feed: Feed, list_item: dict, detail: dict, producer_url: str
) -> None:
    """Update common fields of a Feed (Gtfsfeed or Gtfsrealtimefeed) from JBDA list item and detail."""
    logger.debug(
        "Updating common fields for feed id=%s stable_id=%s",
        getattr(feed, "id", None),
        getattr(feed, "stable_id", None),
    )
    feed.feed_name = detail.get("feed_name")
    feed.provider = list_item.get("organization_name")
    feed.producer_url = producer_url
    feed.license_url = detail.get("feed_license_url")
    feed.feed_contact_email = (
        list_item.get("organization_email")
        if list_item.get("organization_email") != "not_set"
        else None
    )
    feed.status = "active"
    feed.operational_status = "wip"
    feed.note = list_item.get("feed_memo")

    # Ensure a JBDA external id exists; only append if missing.
    jbda_id = feed.stable_id.replace("jbda-", "")
    has_jbda = any(
        (ei.source == "jbda" and ei.associated_id == jbda_id)
        for ei in getattr(feed, "externalids", [])
    )
    if not has_jbda:
        feed.externalids.append(Externalid(associated_id=jbda_id, source="jbda"))
        logger.debug("Appended missing JBDA Externalid for %s", feed.stable_id)

    logger.debug(
        "Updated fields: name=%s provider=%s producer_url_set=%s",
        feed.feed_name,
        feed.provider,
        bool(producer_url),
    )


def _get_or_create_location(db_session: Session, pref_id_raw: Any):
    """
    Map JBDA pref_id (1..47) to JP subdivision name; create or get Location.
    """
    logger.debug("Resolving location for pref_id_raw=%s", pref_id_raw)
    try:
        i = int(str(pref_id_raw).strip())
        code = f"JP-{i:02d}"
        municipality = pycountry.subdivisions.lookup(code).name
    except Exception as e:
        logger.warning(
            "Failed to map pref_id_raw=%s to JP subdivision: %s", pref_id_raw, e
        )
        municipality = None

    loc = create_or_get_location(
        db_session, country="Japan", state_province=municipality, city_name=None
    )
    logger.info(
        "Location resolved for pref_id=%s → %s", pref_id_raw, getattr(loc, "id", None)
    )
    return loc


def _add_related_gtfs_url(
    detail_body: Dict[str, Any],
    db_session: Session,
    rid: str,
    description: str,
    feed: Gtfsfeed,
):
    """
    Add a related GTFS URL (prev/next) if it exists and isn't already present.
    """
    logger.debug("Adding related GTFS URL for feed_id=%s rid=%s", feed.id, rid)
    url = get_gtfs_file_url(detail_body, rid=rid)
    if not url:
        logger.info("No URL available for rid=%s; skipping related link", rid)
        return
    db_rid = "jbda-" + rid
    existing = db_session.scalar(
        select(Feedrelatedlink).where(
            and_(Feedrelatedlink.feed_id == feed.id, Feedrelatedlink.code == db_rid)
        )
    )
    if existing:
        logger.debug("Related link already exists for feed_id=%s rid=%s", feed.id, rid)
        return

    related_link = Feedrelatedlink(
        url=url, description=description, code=db_rid, created_at=datetime.now()
    )
    feed.feedrelatedlinks.append(related_link)
    db_session.flush()
    logger.info("Added related link for feed_id=%s rid=%s url=%s", feed.id, rid, url)


def _add_related_gtfs_urls(
    detail_body: Dict[str, Any], db_session: Session, feed: Gtfsfeed
):
    """Batch add prev/next related URLs (idempotent)."""
    logger.debug("Adding batch of related GTFS URLs for feed_id=%s", feed.id)
    for rid, description in RID_DESCRIPTIONS.items():
        _add_related_gtfs_url(detail_body, db_session, rid, description, feed)


def _extract_api_rt_map(list_item: dict, detail: dict) -> dict[str, Optional[str]]:
    """Map entity_type_name -> url from API payload (tu/vp/sa)."""
    rt_info = (detail.get("real_time") or {}) or (list_item.get("real_time") or {})
    out: dict[str, Optional[str]] = {}
    for url_key, entity_type_name in URLS_TO_ENTITY_TYPES_MAP.items():
        out[entity_type_name] = rt_info.get(url_key) or None
    return out


def _extract_db_rt_map(
    db_session: Session, stable_id_base: str
) -> dict[str, Optional[str]]:
    """Map entity_type_name -> producer_url from DB for existing RT feeds."""
    out: dict[str, Optional[str]] = {"tu": None, "vp": None, "sa": None}
    for et in ("tu", "vp", "sa"):
        sid = f"{stable_id_base}-{et}"
        rt = db_session.scalar(
            select(Gtfsrealtimefeed).where(Gtfsrealtimefeed.stable_id == sid)
        )
        out[et] = getattr(rt, "producer_url", None) if rt else None
    return out


def _fetch_feeds(session_http: requests.Session) -> List[dict]:
    """Fetch the JBDA feeds list or raise on HTTP error."""
    res = session_http.get(FEEDS_URL, timeout=REQUEST_TIMEOUT_S)
    res.raise_for_status()
    payload = res.json() or {}
    return payload.get("body") or []


def _fetch_detail(
    session_http: requests.Session, org_id: str, feed_id: str
) -> Optional[dict]:
    """Fetch one feed's detail body, or raise on HTTP error."""
    detail_url = DETAIL_URL_TMPL.format(org_id=org_id, feed_id=feed_id)
    logger.debug("Detail URL: %s", detail_url)
    dres = session_http.get(detail_url, timeout=REQUEST_TIMEOUT_S)
    dres.raise_for_status()
    return (
        dres.json().get("body", {})
        if dres.headers.get("Content-Type", "").startswith("application/json")
        else {}
    )


def _upsert_rt_feeds(
    db_session: Session,
    stable_id: str,
    list_item: dict,
    detail_body: dict,
    gtfs_feed: Gtfsfeed,
    location,
) -> Tuple[int, int]:
    """
    Upsert RT feeds for available URLs and link them to the schedule feed.
    Returns: (created_rt_delta, linked_refs_delta)
    """
    created_rt = 0
    linked_refs = 0

    rt_info = detail_body.get("real_time") or list_item.get("real_time") or {}
    for url_key, entity_type_name in URLS_TO_ENTITY_TYPES_MAP.items():
        url = rt_info.get(url_key)
        if not url:
            logger.debug(
                "No RT url for key=%s (feed_id=%s)", url_key, list_item.get("feed_id")
            )
            continue

        et = get_or_create_entity_type(db_session, entity_type_name)
        rt_stable_id = f"{stable_id}-{entity_type_name}"
        rt_feed, is_new_rt = get_or_create_feed(
            db_session, Gtfsrealtimefeed, rt_stable_id, "gtfs_rt"
        )

        rt_feed.entitytypes.clear()
        rt_feed.entitytypes.append(et)

        _update_common_feed_fields(rt_feed, list_item, detail_body, url)

        rt_feed.gtfs_feeds.clear()
        rt_feed.gtfs_feeds.append(gtfs_feed)

        try:
            if location and (not rt_feed.locations or len(rt_feed.locations) == 0):
                rt_feed.locations.append(location)
        except AttributeError:
            logger.warning("RT feed model lacks 'locations' relationship; skipping")

        if is_new_rt:
            created_rt += 1
            logger.info(
                "Created RT feed stable_id=%s url_key=%s", rt_stable_id, url_key
            )
        linked_refs += 1

    return created_rt, linked_refs


def _process_feed(
    db_session: Session,
    session_http: requests.Session,
    item: dict,
) -> Tuple[dict, Optional[Feed]]:
    """
    Process a single feed list item end-to-end.
    Returns:
      (deltas_dict, feed_to_publish_or_none)
    """
    org_id = item.get("organization_id")
    feed_id = item.get("feed_id")
    if not org_id or not feed_id:
        logger.warning("Missing organization_id/feed_id in list item; skipping")
        return {
            "created_gtfs": 0,
            "updated_gtfs": 0,
            "created_rt": 0,
            "linked_refs": 0,
            "processed": 0,
        }, None

    # Detail payload
    try:
        dbody = _fetch_detail(session_http, org_id, feed_id)
    except Exception as e:
        logger.exception(
            "Exception during DETAIL request for %s/%s: %s", org_id, feed_id, e
        )
        return {
            "created_gtfs": 0,
            "updated_gtfs": 0,
            "created_rt": 0,
            "linked_refs": 0,
            "processed": 0,
        }, None

    # Validate current GTFS url
    producer_url = get_gtfs_file_url(dbody, rid="current")
    if not producer_url:
        logger.warning("No GTFS URL found for feed %s/%s; skipping", org_id, feed_id)
        return {
            "created_gtfs": 0,
            "updated_gtfs": 0,
            "created_rt": 0,
            "linked_refs": 0,
            "processed": 0,
        }, None

    # Upsert/lookup schedule feed
    stable_id = f"jbda-{org_id}-{feed_id}"
    gtfs_feed, is_new_gtfs = get_or_create_feed(db_session, Gtfsfeed, stable_id, "gtfs")

    # Diff detection
    api_sched_fp = _build_api_schedule_fingerprint(item, dbody, producer_url)
    api_rt_map = _extract_api_rt_map(item, dbody)
    if not is_new_gtfs:
        db_sched_fp = _build_db_schedule_fingerprint(gtfs_feed)
        db_rt_map = _extract_db_rt_map(db_session, stable_id)
        if db_sched_fp == api_sched_fp and db_rt_map == api_rt_map:
            logger.info("No change detected; skipping feed stable_id=%s", stable_id)
            return {
                "created_gtfs": 0,
                "updated_gtfs": 0,
                "created_rt": 0,
                "linked_refs": 0,
                "processed": 1,
            }, None
        diff = {
            k: (db_sched_fp.get(k), api_sched_fp.get(k))
            for k in api_sched_fp
            if db_sched_fp.get(k) != api_sched_fp.get(k)
        }
        diff_rt = {
            k: (db_rt_map.get(k), api_rt_map.get(k))
            for k in api_rt_map
            if db_rt_map.get(k) != api_rt_map.get(k)
        }
        logger.info("Diff %s sched=%s rt=%s", stable_id, diff, diff_rt)

    # Apply schedule fields
    _update_common_feed_fields(gtfs_feed, item, dbody, producer_url)

    # Related links (idempotent)
    _add_related_gtfs_urls(dbody, db_session, gtfs_feed)

    # Location (append only if empty)
    location = _get_or_create_location(db_session, item.get("feed_pref_id"))
    if location and (not gtfs_feed.locations or len(gtfs_feed.locations) == 0):
        gtfs_feed.locations.append(location)

    created_gtfs = 1 if is_new_gtfs else 0
    updated_gtfs = 0 if is_new_gtfs else 1

    # RT upserts + links
    created_rt, linked_refs = _upsert_rt_feeds(
        db_session=db_session,
        stable_id=stable_id,
        list_item=item,
        detail_body=dbody,
        gtfs_feed=gtfs_feed,
        location=location,
    )

    return (
        {
            "created_gtfs": created_gtfs,
            "updated_gtfs": updated_gtfs,
            "created_rt": created_rt,
            "linked_refs": linked_refs,
            "processed": 1,
        },
        gtfs_feed if is_new_gtfs else None,
    )


def _build_api_schedule_fingerprint(
    list_item: dict, detail: dict, producer_url: str
) -> dict:
    """Collect only fields we actually persist on schedule feeds."""
    return {
        "stable_id": f"jbda-{list_item.get('organization_id')}-{list_item.get('feed_id')}",
        "feed_name": detail.get("feed_name"),
        "provider": list_item.get("organization_name"),
        "producer_url": producer_url,
        "license_url": detail.get("feed_license_url"),
        "feed_contact_email": (
            list_item.get("organization_email")
            if list_item.get("organization_email") != "not_set"
            else None
        ),
        "note": list_item.get("feed_memo"),
    }


def _build_db_schedule_fingerprint(feed: Gtfsfeed) -> dict:
    return {
        "stable_id": getattr(feed, "stable_id", None),
        "feed_name": getattr(feed, "feed_name", None),
        "provider": getattr(feed, "provider", None),
        "producer_url": getattr(feed, "producer_url", None),
        "license_url": getattr(feed, "license_url", None),
        "feed_contact_email": getattr(feed, "feed_contact_email", None),
        "note": getattr(feed, "note", None),
    }


@with_db_session
def _import_jbda(db_session: Session, dry_run: bool = True) -> dict:
    """
    Orchestrates the JBDA import: fetch list, iterate, process, batch-commit, then finalize.
    """
    logger.info("Starting JBDA import dry_run=%s", dry_run)
    session_http = requests.Session()

    # Fetch list
    try:
        feeds_list = _fetch_feeds(session_http)
    except Exception as e:
        logger.exception("Exception during FEEDS_URL request")
        return {
            "message": "Failed to fetch JBDA feeds.",
            "error": str(e),
            "params": {"dry_run": dry_run},
            "created_gtfs": 0,
            "updated_gtfs": 0,
            "created_rt": 0,
            "linked_refs": 0,
            "total_processed_items": 0,
        }

    logger.info(
        "Commit batch size (env COMMIT_BATCH_SIZE)=%s",
        os.getenv("COMMIT_BATCH_SIZE", "5"),
    )
    commit_batch_size = int(os.getenv("COMMIT_BATCH_SIZE", 5))

    # Aggregates
    created_gtfs = updated_gtfs = created_rt = linked_refs = total_processed = 0
    feeds_to_publish: List[Feed] = []

    for idx, item in enumerate(feeds_list, start=1):
        try:
            if item.get("feed_is_discontinued"):
                logger.info(
                    "Skipping discontinued feed at index=%d feed_id=%s",
                    idx,
                    item.get("feed_id"),
                )
                continue

            deltas, feed_to_publish = _process_feed(db_session, session_http, item)
            created_gtfs += deltas["created_gtfs"]
            updated_gtfs += deltas["updated_gtfs"]
            created_rt += deltas["created_rt"]
            linked_refs += deltas["linked_refs"]
            total_processed += deltas["processed"]

            if feed_to_publish and not dry_run:
                feeds_to_publish.append(feed_to_publish)

            if not dry_run and (total_processed % commit_batch_size == 0):
                logger.info("Committing batch at total_processed=%d", total_processed)
                try:
                    commit_changes(db_session, feeds_to_publish, total_processed)
                    feeds_to_publish = []  # reset after commit
                except IntegrityError:
                    db_session.rollback()
                    feeds_to_publish = []  # reset even on failure
                    logger.exception(
                        "DB IntegrityError during batch commit at processed=%d",
                        total_processed,
                    )

        except Exception as e:
            logger.exception("Exception processing feed at index=%d: %s", idx, e)
            continue

    if not dry_run:
        commit_changes(db_session, feeds_to_publish, total_processed)

    message = (
        "Dry run: no DB writes performed."
        if dry_run
        else "JBDA import executed successfully."
    )
    summary = {
        "message": message,
        "created_gtfs": created_gtfs,
        "updated_gtfs": updated_gtfs,
        "created_rt": created_rt,
        "linked_refs": linked_refs,
        "total_processed_items": total_processed,
        "params": {"dry_run": dry_run},
    }
    logger.info("Import summary: %s", summary)
    return summary


def commit_changes(
    db_session: Session, feeds_to_publish: list[Feed], total_processed: int
):
    """
    Commit DB changes and trigger dataset downloads for new feeds.
    """
    try:
        logger.info("Commit after processing items (count=%d)", total_processed)
        db_session.commit()
        execution_id = str(uuid.uuid4())
        for feed in feeds_to_publish:
            trigger_dataset_download(feed, execution_id)
    except IntegrityError:
        db_session.rollback()
        logger.exception("Commit failed with IntegrityError; rolled back")
