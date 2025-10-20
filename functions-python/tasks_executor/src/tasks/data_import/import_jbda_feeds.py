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
from typing import Optional, Tuple, Dict, Any, List, Final, Type, TypeVar

import requests
import pycountry
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Entitytype,
    Feedrelatedlink,
)
from shared.helpers.locations import create_or_get_location
from tasks.data_import.data_import_utils import trigger_dataset_download
from google.cloud import pubsub_v1

T = TypeVar("T", bound="Feed")

# --- added logger (no behavioral changes) ---
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
    "next_1": "The next feed URL after the current one",
    "next_2": "The second next feed URL after the current one",
    "prev_1": "The previous feed URL before the current one",
    "prev_2": "The second previous feed URL before the current one",
}


def import_jbda_handler(payload: dict | None = None) -> dict:
    """
    Entry point (cloud function style).

    Payload:
      {
        "dry_run": bool  # optional; default True
      }
    Args:
        payload (dict): The payload containing the task details.
    Returns:
      dict with message, counters, and params.
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
    logger.info(result)
    logger.info(
        "import_jbda_handler result summary: %s",
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


def _get_or_create_entity_type(session: Session, entity_type_name: str) -> Entitytype:
    """
    Get or create an Entitytype by name.
    Args:
        session (Session): SQLAlchemy session.
        entity_type_name (str): Name of the entity type.
    Returns:
        Entitytype: The existing or newly created Entitytype object.
    """
    logger.debug("Looking up Entitytype name=%s", entity_type_name)
    et = session.scalar(select(Entitytype).where(Entitytype.name == entity_type_name))
    if et:
        logger.debug("Found existing Entitytype name=%s", entity_type_name)
        return et
    et = Entitytype(name=entity_type_name)
    session.add(et)
    session.flush()
    logger.info("Created Entitytype name=%s", entity_type_name)
    return et


def _choose_gtfs_file(
    files: List[Dict[str, Any]], rid: str
) -> Optional[Dict[str, Any]]:
    """
    Choose a GTFS file dict from the list by rid, or None if not found.
    Args:
        files (List[Dict[str, Any]]): List of GTFS file dicts.
        rid (str): The rid to match.
    Returns:
        Optional[Dict[str, Any]]: The chosen GTFS file dict or None.
    """
    for f in files:
        if f.get("rid") == rid:
            logger.debug(
                "Matched GTFS file for rid=%s (uid=%s)", rid, f.get("gtfs_file_uid")
            )
            return f
    logger.info("No GTFS file found for rid=%s", rid)
    return None


def get_gtfs_file_url(
    detail_body: Dict[str, Any], rid: str = "current", kind: str = "gtfs_url"
) -> Optional[str]:
    """
    Pick a URL from gtfs_files by rid, with fallback to the most recent when rid='current'.
    kind ∈ {"gtfs_url", "stop_url", "route_url", "tracking_url"}.
    """
    files: List[Dict[str, Any]] = (detail_body or {}).get("gtfs_files") or []
    logger.debug(
        "get_gtfs_file_url(kind=%s, rid=%s) with %d files", kind, rid, len(files)
    )
    chosen = _choose_gtfs_file(files, rid)
    url = (chosen or {}).get(kind) or None
    if url:
        logger.debug("Selected URL for rid=%s kind=%s: %s", rid, kind, url)
    else:
        logger.info("URL not available for rid=%s kind=%s", rid, kind)
    return url


def _get_or_create_feed(
    session: Session, model: Type[T], stable_id: str, data_type: str
) -> Tuple[T, bool]:
    """
    Generic helper to get or create a Feed subclass (Gtfsfeed, Gtfsrealtimefeed)
    by stable_id.

    Args:
        session (Session): SQLAlchemy session.
        model (Type): ORM model class (Gtfsfeed, Gtfsrealtimefeed).
        stable_id (str): Stable ID for the feed.
        data_type (str): Data type string for Feed.data_type ("gtfs", "gtfs_rt").

    Returns:
        Tuple[object, bool]: (feed_instance, created_flag)
    """
    logger.debug(
        "Lookup feed model=%s stable_id=%s",
        getattr(model, "__name__", str(model)),
        stable_id,
    )
    feed = session.scalar(select(model).where(model.stable_id == stable_id))
    if feed:
        logger.info(
            "Found existing %s stable_id=%s id=%s",
            getattr(model, "__name__", str(model)),
            stable_id,
            feed.id,
        )
        return feed, False

    new_id = str(uuid.uuid4())
    feed = model(
        id=new_id,
        data_type=data_type,
        stable_id=stable_id,
    )
    session.add(feed)
    session.flush()
    logger.info(
        "Created %s stable_id=%s id=%s data_type=%s",
        getattr(model, "__name__", str(model)),
        stable_id,
        new_id,
        data_type,
    )
    return feed, True


def _update_common_feed_fields(
    feed: Feed, list_item: dict, detail: dict, producer_url: str
) -> None:
    """
    Update common fields of a Feed (Gtfsfeed or Gtfsrealtimefeed) from JBDA list item and detail.
    Args:
        feed (Feed): The feed object to update.
        list_item (dict): The list item dict from the feeds list.
        detail (dict): The detail dict from the feed detail endpoint.
        producer_url (str): The producer URL to set.
    """
    logger.debug(
        "Updating common fields for feed id=%s stable_id=%s",
        getattr(feed, "id", None),
        getattr(feed, "stable_id", None),
    )
    feed.feed_name = detail.get("feed_name")
    feed.provider = list_item.get("organization_name")
    feed.producer_url = producer_url
    feed.license_url = detail.get("feed_license_url")
    feed.feed_contact_email = list_item.get("organization_email")
    feed.status = "active"
    feed.operational_status = "wip"
    feed.note = list_item.get("feed_memo")
    logger.debug(
        "Updated fields: name=%s provider=%s producer_url_set=%s",
        feed.feed_name,
        feed.provider,
        bool(producer_url),
    )


def _get_or_create_location(db_session: Session, pref_id_raw: Any):
    """
    Map JBDA pref_id (1..47 or zero-padded string) to JP subdivision name.
    Args:
        db_session (Session): SQLAlchemy session.
        pref_id_raw (Any): Raw pref_id from JBDA (int or str).

    Returns:
        Location or None: The Location object for the prefecture, or None if not found.
    """
    logger.debug("Resolving location for pref_id_raw=%s", pref_id_raw)
    try:
        # normalize to 2-digit code (e.g., '01'..'47')
        i = int(str(pref_id_raw).strip())
        code = f"JP-{i:02d}"
        municipality = pycountry.subdivisions.lookup(code).name
        logger.debug(
            "Mapped pref_id=%s to subdivision code=%s (%s)",
            pref_id_raw,
            code,
            municipality,
        )
    except Exception as e:
        logger.warning(
            "Failed to map pref_id_raw=%s to JP subdivision: %s", pref_id_raw, e
        )
        municipality = None

    loc = create_or_get_location(
        db_session,
        country="Japan",
        state_province=municipality,
        city_name=None,
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
    Add a related GTFS URL from detail_body to the database as needed.
    Args:
        detail_body (Dict[str, Any]): The detail body dict from the feed detail endpoint.
        db_session (Session): SQLAlchemy session.
        rid (str): The rid of the GTFS file to add (e.g., "next_1", "previous_1").
    """
    logger.debug("Adding related GTFS URL for feed_id=%s rid=%s", feed.id, rid)
    url = get_gtfs_file_url(detail_body, rid=rid)
    if not url:
        logger.info("No URL available for rid=%s; skipping related link", rid)
        return
    # Check if already exists
    existing = db_session.scalar(
        select(Feedrelatedlink).where(
            and_(
                Feedrelatedlink.feed_id == feed.id,
                Feedrelatedlink.code == rid,
            )
        )
    )
    if existing:
        logger.debug("Related link already exists for feed_id=%s rid=%s", feed.id, rid)
        return

    # Create new related link
    related_link = Feedrelatedlink(
        url=url,
        description=description,
        code=rid,
        created_at=datetime.now(),
    )
    feed.feedrelatedlinks.append(related_link)
    logger.info("Added related link for feed_id=%s rid=%s url=%s", feed.id, rid, url)


def _add_related_gtfs_urls(
    detail_body: Dict[str, Any], db_session: Session, feed: Gtfsfeed
):
    """
    Add related GTFS URLs from detail_body to the database as needed.
    Args:
        detail_body (Dict[str, Any]): The detail body dict from the feed detail endpoint.
        db_session (Session): SQLAlchemy session.
    """
    logger.debug("Adding batch of related GTFS URLs for feed_id=%s", feed.id)
    for rid, description in RID_DESCRIPTIONS.items():
        _add_related_gtfs_url(detail_body, db_session, rid, description, feed)


@with_db_session
def _import_jbda(db_session: Session, dry_run: bool = True) -> dict:
    """
    Import JBDA (Japan GTFS Data API) feeds into MobilityDatabase.

    Scope (per feed):
    - Skip discontinued feeds
    - Upsert GTFS feed (Gtfsfeed) with stable_id = "jbda-<feed_id>"
    - If any real-time URL is present, upsert RT feeds (Gtfsrealtimefeed) with stable_id suffixes:
      tu | vp | sa (trip updates, vehicle positions, service alerts)
    - Link RT → Schedule via ORM relationships

    Idempotent by stable_id. Safe for re-runs.

    Args:
        db_session (Session): SQLAlchemy session.
        dry_run (bool): If True, do not commit changes to the database.
    Returns:
        dict: Result summary with message and counters.
    """
    logger.info("Starting JBDA import dry_run=%s", dry_run)
    execution_id = uuid.uuid4()
    publisher = pubsub_v1.PublisherClient()
    session_http = requests.Session()
    try:
        res = session_http.get(FEEDS_URL, timeout=REQUEST_TIMEOUT_S)
        res.raise_for_status()
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

    payload = res.json() or {}
    feeds_list: List[dict] = payload.get("body") or []
    logger.info(
        "Commit batch size (env GIT_COMMIT_BATCH_SIZE)=%s",
        os.getenv("GIT_COMMIT_BATCH_SIZE", "20"),
    )

    created_gtfs = 0
    updated_gtfs = 0
    created_rt = 0
    linked_refs = 0
    total_processed = 0
    commit_batch_size = int(os.getenv("GIT_COMMIT_BATCH_SIZE", 20))

    for idx, item in enumerate(feeds_list, start=1):
        try:
            # Skip discontinued
            if item.get("feed_is_discontinued") or item.get("is_discontinued"):
                logger.info(
                    "Skipping discontinued feed at index=%d feed_id=%s",
                    idx,
                    item.get("feed_id"),
                )
                continue

            org_id = item.get("organization_id")
            feed_id = item.get("feed_id")
            logger.debug(
                "Processing index=%d org_id=%s feed_id=%s", idx, org_id, feed_id
            )

            if not org_id or not feed_id:
                logger.warning("Missing keys in item at index=%d", idx)
                continue

            stable_id = f"jbda-{feed_id}"
            pref_id = item.get("feed_pref_id")
            location = _get_or_create_location(db_session, pref_id)

            # Fetch detail
            detail_url = DETAIL_URL_TMPL.format(org_id=org_id, feed_id=feed_id)
            logger.debug("Detail URL: %s", detail_url)
            try:
                dres = session_http.get(detail_url, timeout=REQUEST_TIMEOUT_S)
                dres.raise_for_status()
                dbody = (
                    dres.json().get("body", {})
                    if (
                        dres.headers.get("Content-Type", "").startswith(
                            "application/json"
                        )
                    )
                    else {}
                )
                logger.debug(
                    "Detail response ok for %s/%s (has body=%s)",
                    org_id,
                    feed_id,
                    bool(dbody),
                )
            except Exception as e:
                logger.exception(
                    "Exception during DETAIL request for %s/%s: %s", org_id, feed_id, e
                )
                continue

            # Upsert GTFS feed
            producer_url = get_gtfs_file_url(dbody, rid="current", kind="gtfs_url")
            if not producer_url:
                logger.warning(
                    "No GTFS URL found for feed %s/%s; skipping", org_id, feed_id
                )
                continue
            gtfs_feed, is_new_gtfs = _get_or_create_feed(
                db_session, Gtfsfeed, stable_id, "gtfs"
            )
            _update_common_feed_fields(gtfs_feed, item, dbody, producer_url)
            _add_related_gtfs_urls(dbody, db_session, gtfs_feed)
            if location and (not gtfs_feed.locations or len(gtfs_feed.locations) == 0):
                gtfs_feed.locations.append(location)

            created_gtfs += 1 if is_new_gtfs else 0
            updated_gtfs += 0 if is_new_gtfs else 1
            logger.info("GTFS upserted stable_id=%s is_new=%s", stable_id, is_new_gtfs)

            # Real-time feeds (per available URL)
            rt_info = dbody.get("real_time") or item.get("real_time") or {}
            for url_key, entity_type_name in URLS_TO_ENTITY_TYPES_MAP.items():
                url = rt_info.get(url_key)
                if not url:
                    logger.debug("No RT url for key=%s (feed_id=%s)", url_key, feed_id)
                    continue

                et = _get_or_create_entity_type(db_session, entity_type_name)
                rt_stable_id = f"{stable_id}-{entity_type_name}"
                rt_feed, is_new_rt = _get_or_create_feed(
                    db_session, Gtfsrealtimefeed, rt_stable_id, "gtfs_rt"
                )

                rt_feed.entitytypes.clear()
                rt_feed.entitytypes.append(et)

                # common fields
                _update_common_feed_fields(rt_feed, item, dbody, url)

                rt_feed.gtfs_feeds.clear()
                rt_feed.gtfs_feeds.append(gtfs_feed)

                # locations
                try:
                    # Only set location if not already set (do not overwrite)
                    if location and (
                        not rt_feed.locations or len(rt_feed.locations) == 0
                    ):
                        rt_feed.locations.append(location)
                except AttributeError:
                    logger.warning(
                        "RT feed model lacks 'locations' relationship; skipping"
                    )

                if is_new_rt:
                    created_rt += 1
                    logger.info(
                        "Created RT feed stable_id=%s url_key=%s", rt_stable_id, url_key
                    )
                linked_refs += 1

            total_processed += 1
            if is_new_gtfs:
                trigger_dataset_download(gtfs_feed, execution_id, publisher)

            if not dry_run and (total_processed % commit_batch_size == 0):
                logger.info("Committing batch at total_processed=%d", total_processed)
                try:
                    db_session.commit()
                except IntegrityError:
                    db_session.rollback()
                    logger.exception(
                        "DB IntegrityError during batch commit for %s/%s",
                        org_id,
                        feed_id,
                    )
        except Exception as e:
            logger.exception("Exception processing feed at index=%d: %s", idx, e)
            continue

    if not dry_run:
        try:
            logger.info(
                "Final commit after processing all items (count=%d)", total_processed
            )
            db_session.commit()
        except IntegrityError:
            db_session.rollback()
            logger.exception("Final commit failed with IntegrityError; rolled back")

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
