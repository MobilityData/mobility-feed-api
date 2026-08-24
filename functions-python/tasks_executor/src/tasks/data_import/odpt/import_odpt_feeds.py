#!/usr/bin/env python3
#
#   MobilityData 2026
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
from typing import Optional, Tuple, List, Final, TypeVar

import requests
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.common.locations_utils import create_or_get_location
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Externalid,
)
from shared.notifications.notification_event_service import emit_url_replaced
from tasks.data_import.data_import_utils import (
    commit_changes,
    deprecate_stale_feeds,
    get_or_create_entity_type,
    get_or_create_feed,
)

T = TypeVar("T", bound="Feed")

logger = logging.getLogger(__name__)

ODPT_METADATA_API: Final[str] = (
    "https://members-portal.odpt.org/api/v1/resources?license={}&format={}"
)
PUBLIC_GTFS_ENDPOINT: Final[str] = (
    "https://api-public.odpt.org/api/v4/files/odpt/{}/{}.zip?date={}"
)
OPEN_LICENSES = ["ccby4", "cc0"]
REQUEST_TIMEOUT_S: Final[int] = 60

# Maps an ODPT feed item's RT URL field to its GTFS-RT entity type code.
URLS_TO_ENTITY_TYPES_MAP: Final[dict[str, str]] = {
    "trip_update": "tu",
    "vehicle_endpoint": "vp",
    "alert": "sa",
}

# ODPT only exposes a license_type code; map the open licenses we import to their canonical URL.
LICENSE_URL_MAP: Final[dict[str, str]] = {
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC0": "https://creativecommons.org/publicdomain/zero/1.0/",
}

# Feeds that ODPT serves from api-public.odpt.org but never advertises through
# ODPT_METADATA_API: they are published via ODPT's token-gated developer catalog
# instead, under a different path namespace (/api/v4/files/<org>/data/<file>.zip)
# that PUBLIC_GTFS_ENDPOINT cannot express -- note the absent "odpt" segment and
# "date" parameter. They carry an explicit "gtfs_endpoint" for that reason.
#
# These are declared as ordinary feed items, rather than seeded straight into the DB,
# so they flow through the same per-item processing as portal feeds -- in particular
# so their stable_ids reach processed_stable_ids and survive the stale sweep.
STATIC_FEEDS: Final[List[dict]] = [
    {
        "org_label": "Toei",
        "dataset_label": "ToeiBus",
        "org_name_ja": "東京都交通局",
        "org_name_en": "Tokyo Metropolitan Bureau of Transportation",
        "dataset_name_ja": "都営バス",
        "dataset_name_en": "Toei Bus",
        "license_type": "CC BY 4.0",
        "gtfs_endpoint": (
            "https://api-public.odpt.org/api/v4/files/Toei/data/ToeiBus-GTFS.zip"
        ),
        "vehicle_endpoint": "https://api-public.odpt.org/api/v4/gtfs/realtime/ToeiBus",
        "trip_update": None,
        "alert": None,
    },
    {
        "org_label": "Toei",
        "dataset_label": "ToeiTrain",
        "org_name_ja": "東京都交通局",
        "org_name_en": "Tokyo Metropolitan Bureau of Transportation",
        "dataset_name_ja": "都営地下鉄・日暮里舎人ライナー・都電荒川線",
        "dataset_name_en": "Toei Subway, Nippori-Toneri Liner and Toden Arakawa Line",
        "license_type": "CC BY 4.0",
        "gtfs_endpoint": (
            "https://api-public.odpt.org/api/v4/files/Toei/data/Toei-Train-GTFS.zip"
        ),
        "vehicle_endpoint": "https://api-public.odpt.org/api/v4/gtfs/realtime/toei_odpt_train_vehicle",
        "trip_update": "https://api-public.odpt.org/api/v4/gtfs/realtime/toei_odpt_train_trip_update",
        "alert": "https://api-public.odpt.org/api/v4/gtfs/realtime/toei_odpt_train_alert",
    },
]


def import_odpt_handler(payload: dict | None = None) -> dict:
    """
    Cloud Function entrypoint.
    Payload: {"dry_run": bool} (default True)
    """
    payload = payload or {}
    logger.info("import_odpt_handler called with payload=%s", payload)

    dry_run_raw = payload.get("dry_run", True)
    dry_run = (
        dry_run_raw
        if isinstance(dry_run_raw, bool)
        else str(dry_run_raw).lower() == "true"
    )
    logger.info("Parsed dry_run=%s (raw=%s)", dry_run, dry_run_raw)

    result = _import_odpt(dry_run=dry_run)
    logger.info(
        "import_odpt_handler summary: %s",
        {
            k: result.get(k)
            for k in (
                "message",
                "created_gtfs",
                "updated_gtfs",
                "created_gtfs_rt",
                "updated_gtfs_rt",
                "deprecated",
                "linked_refs",
                "total_processed_items",
            )
        },
    )
    return result


def _fetch_feeds(session_http: requests.Session) -> List[dict]:
    """
    Fetch the ODPT feeds list by querying the ODPT metadata API for each open license,
    then flattening each organization's datasets into a feed dict. Raises on HTTP error.
    """
    feeds: List[dict] = []
    for license_key in OPEN_LICENSES:
        metadata_url = ODPT_METADATA_API.format(license_key, "gtfs")
        logger.debug(
            "Fetching ODPT metadata for license=%s: %s", license_key, metadata_url
        )
        res = session_http.get(metadata_url, timeout=REQUEST_TIMEOUT_S)
        res.raise_for_status()

        for org in res.json() or []:
            org_label = org.get("label")
            org_name_ja = org.get("name_ja")
            org_name_en = org.get("name_en")

            for dataset in org.get("datasets") or []:
                dataset_label = dataset.get("label")
                dataset_name_ja = dataset.get("name_ja")
                dataset_name_en = dataset.get("name_en")
                license_type = dataset.get("license_type")

                gtfs_endpoint = PUBLIC_GTFS_ENDPOINT.format(
                    org_label, dataset_label, "current"
                )
                vehicle_endpoint = (dataset.get("vehicle_position") or {}).get("url")
                trip_update = (dataset.get("trip_update") or {}).get("url")
                alert = (dataset.get("alert") or {}).get("url")

                feeds.append(
                    {
                        "org_label": org_label,
                        "dataset_label": dataset_label,
                        "org_name_ja": org_name_ja,
                        "org_name_en": org_name_en,
                        "dataset_name_ja": dataset_name_ja,
                        "dataset_name_en": dataset_name_en,
                        "license_type": license_type,
                        "gtfs_endpoint": gtfs_endpoint,
                        "vehicle_endpoint": vehicle_endpoint,
                        "trip_update": trip_update,
                        "alert": alert,
                    }
                )

    logger.info(
        "Fetched %d ODPT feeds across %d license(s)", len(feeds), len(OPEN_LICENSES)
    )
    return feeds


def _get_license_url(license_type: Optional[str]) -> Optional[str]:
    """Map an ODPT license_type code (e.g. 'ccby4', 'cc0') to its canonical license URL."""
    if not license_type:
        return None
    url = LICENSE_URL_MAP.get(license_type)
    if not url:
        logger.warning(
            "Unknown ODPT license_type=%s; license_url left unset", license_type
        )
    return url


def _update_common_feed_fields(feed: Feed, item: dict, producer_url: str) -> None:
    """Update common fields of a Feed (Gtfsfeed or Gtfsrealtimefeed) from an ODPT feed item."""
    logger.debug(
        "Updating common fields for feed id=%s stable_id=%s",
        getattr(feed, "id", None),
        getattr(feed, "stable_id", None),
    )
    feed.feed_name = item.get("dataset_name_ja") or item.get("dataset_name_en")
    feed.provider = item.get("org_name_ja") or item.get("org_name_en")
    feed.producer_url = producer_url
    feed.license_url = _get_license_url(item.get("license_type"))
    # In the event that the feed was previously deprecated, reactivate it. This occurs
    # when a feed was previously swept as stale but has now reappeared in the source API.
    if feed.status == "deprecated":
        feed.status = "active"
    feed.operational_status = "published"

    # Ensure an ODPT external id exists; only append if missing.
    odpt_id = feed.stable_id.replace("odpt-", "")
    has_odpt = any(
        (ei.source == "odpt" and ei.associated_id == odpt_id)
        for ei in getattr(feed, "externalids", [])
    )
    if not has_odpt:
        feed.externalids.append(Externalid(associated_id=odpt_id, source="odpt"))
        logger.debug("Appended missing ODPT Externalid for %s", feed.stable_id)

    logger.debug(
        "Updated fields: name=%s provider=%s producer_url_set=%s",
        feed.feed_name,
        feed.provider,
        bool(producer_url),
    )


def _get_or_create_location(db_session: Session):
    """
    ODPT feed items carry no prefecture/municipality info (unlike JBDA's feed_pref_id);
    create or get the country-level Location for Japan.
    """
    loc = create_or_get_location(
        db_session, country="Japan", state_province=None, city_name=None
    )
    logger.info("Location resolved for ODPT feed -> %s", getattr(loc, "id", None))
    return loc


def _extract_api_rt_map(item: dict) -> dict[str, Optional[str]]:
    """Map entity_type_name -> url from the ODPT item (tu/vp/sa)."""
    return {
        entity_type_name: item.get(field) or None
        for field, entity_type_name in URLS_TO_ENTITY_TYPES_MAP.items()
    }


def _extract_db_rt_map(
    db_session: Session,
    stable_id_base: str,
    api_rt_map: dict[str, Optional[str]] | None = None,
) -> Tuple[dict[str, Optional[str]], bool]:
    """
    Map entity_type_name -> producer_url from DB for existing RT feeds.

    Also reports whether any RT feed that the API currently advertises (per
    api_rt_map) is sitting in the deprecated/unpublished state and therefore needs
    reactivating. Computed from the same queries, so this costs no extra round-trips.

    Returns: (producer_url_by_entity_type, needs_reactivation)
    """
    out: dict[str, Optional[str]] = {"tu": None, "vp": None, "sa": None}
    needs_reactivation = False
    for et in ("tu", "vp", "sa"):
        sid = f"{stable_id_base}-{et}"
        rt = db_session.scalar(
            select(Gtfsrealtimefeed).where(Gtfsrealtimefeed.stable_id == sid)
        )
        out[et] = getattr(rt, "producer_url", None) if rt else None
        # Only RT feeds the API still advertises are candidates for reactivation;
        # any feeds absent from the API should stay deprecated and be swept.
        if rt is not None and (api_rt_map or {}).get(et):
            if rt.status == "deprecated" or rt.operational_status == "unpublished":
                needs_reactivation = True
    return out, needs_reactivation


def _upsert_rt_feeds(
    db_session: Session,
    stable_id: str,
    item: dict,
    gtfs_feed: Gtfsfeed,
    location,
    processed_stable_ids: set[str],
) -> Tuple[int, int, int]:
    """
    Upsert RT feeds for available URLs and link them to the schedule feed.
    Returns: (created_rt_delta, updated_rt_delta, linked_refs_delta)
    """
    created_rt = 0
    updated_rt = 0
    linked_refs = 0

    # Mark every RT sub-feed present in this item as "seen" up front, decoupled from
    # the processing loop below: if one entity type raises mid-loop, entity types
    # after it would otherwise go unmarked and be wrongly swept as stale even though
    # they are still published by the source.
    for field, entity_type_name in URLS_TO_ENTITY_TYPES_MAP.items():
        if item.get(field):
            processed_stable_ids.add(f"{stable_id}-{entity_type_name}")

    for field, entity_type_name in URLS_TO_ENTITY_TYPES_MAP.items():
        url = item.get(field)
        if not url:
            logger.debug(
                "No RT url for field=%s (dataset_label=%s)",
                field,
                item.get("dataset_label"),
            )
            continue

        et = get_or_create_entity_type(db_session, entity_type_name)
        rt_stable_id = f"{stable_id}-{entity_type_name}"
        rt_feed, is_new_rt = get_or_create_feed(
            db_session, Gtfsrealtimefeed, rt_stable_id, "gtfs_rt"
        )

        rt_feed.entitytypes.clear()
        rt_feed.entitytypes.append(et)

        # Snapshot the "changed?" state before _update_common_feed_fields overwrites producer_url.
        producer_url_changed = not is_new_rt and rt_feed.producer_url != url
        _update_common_feed_fields(rt_feed, item, url)

        rt_feed.gtfs_feeds.clear()
        rt_feed.gtfs_feeds.append(gtfs_feed)

        try:
            if location and (not rt_feed.locations or len(rt_feed.locations) == 0):
                rt_feed.locations.append(location)
        except AttributeError:
            logger.warning("RT feed model lacks 'locations' relationship; skipping")

        if is_new_rt:
            created_rt += 1
            logger.info("Created RT feed stable_id=%s field=%s", rt_stable_id, field)
        elif producer_url_changed:
            updated_rt += 1
            logger.info("Updated RT feed stable_id=%s field=%s", rt_stable_id, field)
        linked_refs += 1

    return created_rt, updated_rt, linked_refs


def _process_feed(
    db_session: Session,
    session_http: requests.Session,
    item: dict,
    location,
    processed_stable_ids: set[str],
) -> Tuple[dict, Optional[Feed]]:
    """
    Process a single feed list item end-to-end.
    `location` is resolved once per run by the caller (it's always Japan for ODPT)
    and just attached here, rather than re-queried/created for every feed.
    `processed_stable_ids` is mutated in place with every stable_id seen this run
    (schedule and RT), so the caller's stale-feed sweep knows what is still present.
    Returns:
      (deltas_dict, feed_to_publish_or_none)
    """
    org_label = item.get("org_label")
    dataset_label = item.get("dataset_label")
    if not org_label or not dataset_label:
        logger.warning("Missing org_label/dataset_label in list item; skipping")
        return {
            "created_gtfs": 0,
            "updated_gtfs": 0,
            "created_gtfs_rt": 0,
            "updated_gtfs_rt": 0,
            "linked_refs": 0,
            "processed": 0,
        }, None

    # Validate current GTFS url.
    producer_url = item.get("gtfs_endpoint")
    if not producer_url:
        logger.warning(
            "No GTFS URL found for feed %s/%s; skipping", org_label, dataset_label
        )
        return {
            "created_gtfs": 0,
            "updated_gtfs": 0,
            "created_gtfs_rt": 0,
            "updated_gtfs_rt": 0,
            "linked_refs": 0,
            "processed": 0,
        }, None

    # Upsert/lookup schedule feed.
    stable_id = f"odpt-{org_label}-{dataset_label}"
    # Mark presence before the upsert: if get_or_create_feed's flush fails
    # transiently, this feed is still live at the source and must not be swept.
    processed_stable_ids.add(stable_id)
    gtfs_feed, is_new_gtfs = get_or_create_feed(db_session, Gtfsfeed, stable_id, "gtfs")

    # Diff detection
    if not is_new_gtfs:
        api_sched_fp = _build_api_schedule_fingerprint(item, producer_url)
        api_rt_map = _extract_api_rt_map(item)
        db_sched_fp = _build_db_schedule_fingerprint(gtfs_feed)
        db_rt_map, rt_needs_reactivation = _extract_db_rt_map(
            db_session, stable_id, api_rt_map
        )
        # A feed that was previously swept as stale and has now reappeared must be
        # reactivated even when nothing else changed -- the fingerprints deliberately
        # cover only the fields we persist from the API, not status/operational_status,
        # so an unchanged-but-deprecated feed would otherwise return early here and
        # stay hidden forever.
        needs_reactivation = (
            gtfs_feed.status == "deprecated"
            or gtfs_feed.operational_status == "unpublished"
            or rt_needs_reactivation
        )
        if (
            db_sched_fp == api_sched_fp
            and db_rt_map == api_rt_map
            and not needs_reactivation
        ):
            logger.info("No change detected; skipping feed stable_id=%s", stable_id)
            return {
                "created_gtfs": 0,
                "updated_gtfs": 0,
                "created_gtfs_rt": 0,
                "updated_gtfs_rt": 0,
                "linked_refs": 0,
                "processed": 1,
            }, None
        if needs_reactivation:
            logger.info(
                "Reactivating previously deprecated feed stable_id=%s", stable_id
            )
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
        if "producer_url" in diff:
            old_url, new_url = diff["producer_url"]
            if old_url and new_url and old_url != new_url:
                emit_url_replaced(
                    feed_stable_id=stable_id,
                    old_url=old_url,
                    new_url=new_url,
                    source="odpt_import",
                )

    # Apply schedule fields
    _update_common_feed_fields(gtfs_feed, item, producer_url)

    # Location (append only if empty)
    if location and (not gtfs_feed.locations or len(gtfs_feed.locations) == 0):
        gtfs_feed.locations.append(location)

    created_gtfs = 1 if is_new_gtfs else 0
    updated_gtfs = 0 if is_new_gtfs else 1

    # RT upserts + links
    created_gtfs_rt, updated_gtfs_rt, linked_refs = _upsert_rt_feeds(
        db_session=db_session,
        stable_id=stable_id,
        item=item,
        gtfs_feed=gtfs_feed,
        location=location,
        processed_stable_ids=processed_stable_ids,
    )

    return (
        {
            "created_gtfs": created_gtfs,
            "updated_gtfs": updated_gtfs,
            "created_gtfs_rt": created_gtfs_rt,
            "updated_gtfs_rt": updated_gtfs_rt,
            "linked_refs": linked_refs,
            "processed": 1,
        },
        gtfs_feed if is_new_gtfs else None,
    )


def _build_api_schedule_fingerprint(item: dict, producer_url: str) -> dict:
    """Collect only fields we actually persist on schedule feeds."""
    return {
        "stable_id": f"odpt-{item.get('org_label')}-{item.get('dataset_label')}",
        "feed_name": item.get("dataset_name_ja") or item.get("dataset_name_en"),
        "provider": item.get("org_name_ja") or item.get("org_name_en"),
        "producer_url": producer_url,
        "license_url": _get_license_url(item.get("license_type")),
    }


def _build_db_schedule_fingerprint(feed: Gtfsfeed) -> dict:
    return {
        "stable_id": getattr(feed, "stable_id", None),
        "feed_name": getattr(feed, "feed_name", None),
        "provider": getattr(feed, "provider", None),
        "producer_url": getattr(feed, "producer_url", None),
        "license_url": getattr(feed, "license_url", None),
    }


@with_db_session
def _import_odpt(db_session: Session, dry_run: bool = True) -> dict:
    """
    Orchestrates the ODPT import: fetch by license and organization, process, batch-commit
    """
    logger.info("Starting ODPT import dry_run=%s", dry_run)
    session_http = requests.Session()

    # Fetch list
    try:
        portal_feeds = _fetch_feeds(session_http)
    except Exception as e:
        logger.exception("Exception during ODPT_METADATA_API request")
        return {
            "message": "Failed to fetch ODPT feeds.",
            "error": str(e),
            "params": {"dry_run": dry_run},
            "created_gtfs": 0,
            "updated_gtfs": 0,
            "created_gtfs_rt": 0,
            "updated_gtfs_rt": 0,
            "deprecated": 0,
            "linked_refs": 0,
            "total_processed_items": 0,
        }

    # Appended here rather than inside _fetch_feeds so that `portal_feeds` remains a
    # faithful record of what the source actually returned. The stale sweep below keys
    # off that, and must not read a list made up solely of our own static entries as
    # evidence that the portal answered.
    # Copied so a feed item mutated downstream can't corrupt the module-level constant
    # for the next invocation -- Cloud Function instances are reused between runs.
    feeds_list = portal_feeds + [dict(feed) for feed in STATIC_FEEDS]
    logger.info(
        "Feed list assembled: %d from portal + %d static = %d total",
        len(portal_feeds),
        len(STATIC_FEEDS),
        len(feeds_list),
    )

    logger.info(
        "Commit batch size (env COMMIT_BATCH_SIZE)=%s",
        os.getenv("COMMIT_BATCH_SIZE", "5"),
    )
    commit_batch_size = int(os.getenv("COMMIT_BATCH_SIZE", 5))

    # ODPT feeds are always located in Japan, so resolve/create that Location once
    # per run instead of on every feed.
    location = _get_or_create_location(db_session) if feeds_list else None

    # Aggregates
    created_gtfs = updated_gtfs = created_gtfs_rt = updated_gtfs_rt = 0
    linked_refs = total_processed = 0
    feeds_to_publish: List[Feed] = []
    changed_feed_stable_ids: List[str] = []
    processed_stable_ids: set[str] = set()

    for idx, item in enumerate(feeds_list, start=1):
        try:
            deltas, feed_to_publish = _process_feed(
                db_session, session_http, item, location, processed_stable_ids
            )
            created_gtfs += deltas["created_gtfs"]
            updated_gtfs += deltas["updated_gtfs"]
            created_gtfs_rt += deltas["created_gtfs_rt"]
            updated_gtfs_rt += deltas["updated_gtfs_rt"]
            linked_refs += deltas["linked_refs"]
            total_processed += deltas["processed"]

            if feed_to_publish and not dry_run:
                feeds_to_publish.append(feed_to_publish)

            # Track changed feeds for website cache revalidation
            if not dry_run and (deltas["created_gtfs"] or deltas["updated_gtfs"]):
                org_label = item.get("org_label")
                dataset_label = item.get("dataset_label")
                if org_label and dataset_label:
                    changed_feed_stable_ids.append(f"odpt-{org_label}-{dataset_label}")

            if not dry_run and (total_processed % commit_batch_size == 0):
                logger.info("Committing batch at total_processed=%d", total_processed)
                try:
                    commit_changes(
                        db_session,
                        feeds_to_publish,
                        total_processed,
                        changed_feed_stable_ids,
                    )
                    feeds_to_publish = []  # reset after commit
                    changed_feed_stable_ids = []  # reset after commit
                except IntegrityError:
                    db_session.rollback()
                    feeds_to_publish = []  # reset even on failure
                    changed_feed_stable_ids = []  # reset even on failure
                    logger.exception(
                        "DB IntegrityError during batch commit at processed=%d",
                        total_processed,
                    )

        except Exception as e:
            logger.exception("Exception processing feed at index=%d: %s", idx, e)
            continue

    # Deprecate feeds the source no longer advertises. Run unconditionally so a
    # dry run can report what *would* be deprecated; the dry-run rollback below
    # still guarantees nothing persists.
    if portal_feeds:
        newly_deprecated = deprecate_stale_feeds(
            db_session, "odpt-", processed_stable_ids
        )
        changed_feed_stable_ids.extend(newly_deprecated)
    else:
        # IMPORTANT: A successful-but-empty fetch from ODPT source is not evidence
        # that every feed was withdrawn. Sweeping here would deprecate the entire
        # odpt- catalog in one run so that is avoided by setting newly_deprecated empty
        newly_deprecated = []
        logger.warning(
            "Skipping stale-feed deprecation sweep: the portal returned zero feeds; "
            "refusing to deprecate the entire odpt- catalog."
        )

    if not dry_run:
        commit_changes(
            db_session, feeds_to_publish, total_processed, changed_feed_stable_ids
        )
    else:
        # get_or_create_feed/get_or_create_entity_type flush new rows into the session
        # regardless of dry_run, and @with_db_session's start_db_session() commits
        # unconditionally whenever this function returns without raising. Without this
        # rollback, a "dry run" silently persists everything that was staged.
        db_session.rollback()
        logger.info("Dry run: rolled back all staged changes, no DB writes performed.")

    message = (
        "Dry run: no DB writes performed."
        if dry_run
        else "ODPT import executed successfully."
    )
    summary = {
        "message": message,
        "created_gtfs": created_gtfs,
        "updated_gtfs": updated_gtfs,
        "created_gtfs_rt": created_gtfs_rt,
        "updated_gtfs_rt": updated_gtfs_rt,
        "deprecated": len(newly_deprecated),
        "linked_refs": linked_refs,
        "total_processed_items": total_processed,
        "params": {"dry_run": dry_run},
    }
    logger.info("Import summary: %s", summary)
    return summary
