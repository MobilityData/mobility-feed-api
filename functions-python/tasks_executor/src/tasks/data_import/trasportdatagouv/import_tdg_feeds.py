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
from typing import Any, Dict, List, Optional, Tuple

import requests
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.common.locations_utils import create_or_get_location
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Externalid,
    Location,
)
from shared.helpers.pub_sub import trigger_dataset_download
from tasks.data_import.data_import_utils import (
    get_or_create_feed,
    get_or_create_entity_type,
    get_license,
)

logger = logging.getLogger(__name__)

TDG_BASE = "https://transport.data.gouv.fr"
TDG_DATASETS_URL = f"{TDG_BASE}/api/datasets?format=gtfs"
REQUEST_TIMEOUT_S = 60

GTFS_FORMAT = "GTFS"
GTFS_RT_FORMAT = "gtfs-rt"

LICENSE_URL_MAP = {
    "odc-odbl": {
        "url": "https://opendatacommons.org/licenses/odbl/1.0/",
        "id": "ODbL-1.0",
    },
    "mobility-licence": {
        "url": "https://wiki.lafabriquedesmobilites.fr/wiki/Licence_Mobilit%C3%A9s",
    },
    "fr-lo": {
        "url": "https://www.data.gouv.fr/pages/legal/licences/etalab-2.0",
        "id": "etalab-2.0",
    },
    "lov2": {
        "url": "https://www.data.gouv.fr/pages/legal/licences/etalab-2.0",
        "id": "etalab-2.0",
    },
}

ENTITY_TYPES_MAP = {
    "trip_updates": "tu",
    "vehicle_positions": "vp",
    "service_alerts": "sa",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _get_license_url(license_id: Optional[str]) -> Optional[str]:
    """
    Map TDG license ID to URL if known.
    """
    if not license_id:
        return None
    return LICENSE_URL_MAP.get(license_id.lower(), {}).get("url")


def _probe_head_format(
    session_http: requests.Session, url: str
) -> Tuple[Optional[int], Optional[str], str]:
    """
    HEAD probe to detect basic content type (zip/csv/json/protobuf).
    Returns: (status_code, content_type, detected_format)
    """
    if not url:
        return None, None, "unknown"

    detected_format = "unknown"
    try:
        resp = session_http.head(url, allow_redirects=True, timeout=15)
        status_code = resp.status_code
        content_type = resp.headers.get("Content-Type", "") or ""
    except Exception as e:
        logger.warning("HEAD probe failed for %s: %s", url, e)
        return None, None, "unknown"

    lowered = (content_type or "").lower()
    if "zip" in lowered:
        detected_format = "zip"
    elif "csv" in lowered:
        detected_format = "csv"
    elif "protobuf" in lowered or "x-protobuf" in lowered:
        detected_format = "protobuf"
    elif "json" in lowered:
        detected_format = "json"

    return status_code, content_type, detected_format


def _get_entity_types_from_resource(resource: dict) -> List[str]:
    """
    Extract entity types from TDG resource `features` field.
    """
    features = resource.get("features", []) or []
    entity_types = []
    for feature in features:
        if isinstance(feature, str) and feature.lower() in ENTITY_TYPES_MAP:
            entity_types.append(ENTITY_TYPES_MAP.get(feature.lower()))
    return entity_types


def _fetch_tdg_datasets(session_http: requests.Session) -> List[dict]:
    """
    Fetch TDG datasets for GTFS import.

    NOTE: This currently fetches a single page like your CSV helper.
    If TDG is paginated and you need everything, plug in pagination here.
    """
    logger.info("Fetching TDG datasets from %s", TDG_DATASETS_URL)
    res = session_http.get(TDG_DATASETS_URL, timeout=REQUEST_TIMEOUT_S)
    res.raise_for_status()
    payload = res.json()
    if isinstance(payload, list):
        return payload
    return payload or []


# ---------------------------------------------------------------------------
# Location helpers
# ---------------------------------------------------------------------------


def _get_tdg_locations(db_session: Session, dataset: dict) -> List[Any]:
    """
    Map TDG `covered_area` entries to Location rows.

    covered_area items look like:
      {
        "type": "pays|region|departement|epci|commune",
        "nom": "<name>",
        "insee": "<code>"
      }

    Rules (from your assumption):
      - If type == 'pays', use that as the country.
      - If there is no 'pays', assume country = 'France'.
      - region/departement → state_province
      - commune/epci      → municipality (city_name)
    """
    covered_areas = dataset.get("covered_area", []) or []

    # Try to detect a country from 'pays' if present
    country_name: Optional[str] = None
    for area in covered_areas:
        if area.get("type") == "pays":
            country_name = area.get("nom") or "France"
            break

    if not country_name:
        country_name = "France"

    locations: List[Any] = []

    for area in covered_areas:
        a_type = area.get("type")
        name = area.get("nom")

        if not name:
            continue

        state_province: Optional[str] = None
        if a_type in ("region", "departement", "commune", "epci"):
            state_province = name
        elif a_type == "pays":
            # we only encode it as a country-level location
            pass

        loc = create_or_get_location(
            db_session,
            country=country_name,
            state_province=state_province,
            city_name=None,
        )
        locations.append(loc)

    return locations


# ---------------------------------------------------------------------------
# Feed helpers
# ---------------------------------------------------------------------------


def _deprecate_stale_feeds(db_session, processed_stable_ids):
    """
    Deprecate TDG feeds not seen in this import run.
    """
    logger.info("Deprecating stale TDG feeds not in processed_stable_ids")
    tdg_feeds = (
        db_session.query(Feed)
        .filter(Feed.stable_id.like("tdg-%"))
        .filter(~Feed.stable_id.in_(processed_stable_ids))
        .all()
    )
    logger.info("Found %d tdg_feeds stale stable_ids", len(tdg_feeds))
    deprecated_count = 0
    for feed in tdg_feeds:
        if feed.status != "deprecated":
            feed.status = "deprecated"
            deprecated_count += 1
            logger.info("Deprecated stale TDG feed stable_id=%s", feed.stable_id)

    logger.info("Total deprecated stale TDG feeds: %d", deprecated_count)


def _ensure_tdg_external_id(feed: Feed, resource_id: str) -> None:
    """
    Ensure that an Externalid(source='tdg', associated_id=<resource_id>) exists.
    """
    if not resource_id:
        return

    has_tdg = any(
        (ei.source == "tdg" and ei.associated_id == resource_id)
        for ei in getattr(feed, "externalids", [])
    )
    if not has_tdg:
        feed.externalids.append(Externalid(associated_id=resource_id, source="tdg"))
        logger.debug("Appended missing TDG Externalid for %s", feed.stable_id)


def _compute_status_from_end_date(metadata: dict) -> str:
    """
    Use metadata.end_date to mark schedule as active/inactive.
    Falls back to 'active' if missing or invalid.
    """
    end_date_raw = metadata.get("end_date")
    if not end_date_raw:
        return "active"
    try:
        end_date = datetime.strptime(end_date_raw, "%Y-%m-%d").date()
    except Exception:
        return "active"
    return "active" if datetime.now().date() <= end_date else "inactive"


def _update_common_tdg_fields(
    feed: Feed,
    dataset: dict,
    resource: dict,
    producer_url: str,
    locations: List[Location],
    db_session: Session,
) -> None:
    """
    Update common fields for both schedule GTFS and RT from TDG dataset + resource.
    """
    feed.feed_name = dataset.get("title")
    publisher = (dataset.get("publisher") or {}).get("name")
    feed.provider = publisher
    feed.producer_url = producer_url

    feed.status = _compute_status_from_end_date((resource.get("metadata") or {}) or {})
    feed.operational_status = "wip"

    feed.license_url = _get_license_url(dataset.get("licence"))
    feed_license = get_license(
        db_session, LICENSE_URL_MAP.get(dataset.get("licence"), {}).get("id")
    )
    if feed_license:
        feed.license = feed_license
    # Use locations only if not already set
    if locations and (not feed.locations or len(feed.locations) == 0):
        feed.locations = locations

    logger.debug(
        "Updated TDG feed fields: stable_id=%s provider=%s status=%s",
        feed.stable_id,
        feed.provider,
        feed.status,
    )


# ---------------------------------------------------------------------------
# Fingerprints (for diffing)
# ---------------------------------------------------------------------------


def _build_api_schedule_fingerprint_tdg(
    dataset: dict,
    resource: dict,
    producer_url: str,
) -> dict:
    return {
        "stable_id": f"tdg-{resource.get('id')}",
        "feed_name": dataset.get("title"),
        "provider": (dataset.get("publisher") or {}).get("name"),
        "producer_url": producer_url,
        "license_url": _get_license_url(dataset.get("licence")),
    }


def _build_db_schedule_fingerprint_tdg(feed: Gtfsfeed) -> dict:
    return {
        "stable_id": getattr(feed, "stable_id", None),
        "feed_name": getattr(feed, "feed_name", None),
        "provider": getattr(feed, "provider", None),
        "producer_url": getattr(feed, "producer_url", None),
        "license_url": getattr(feed, "license_url", None),
    }


def _build_api_rt_fingerprint_tdg(
    dataset: dict,
    producer_url: str,
    static_gtfs_stable_ids: List[str],
    rt_stable_id: str,
) -> dict:
    return {
        "stable_id": rt_stable_id,
        "feed_name": dataset.get("title"),
        "provider": (dataset.get("publisher") or {}).get("name"),
        "producer_url": producer_url,
        "license_url": _get_license_url(dataset.get("licence")),
        "static_refs": sorted(static_gtfs_stable_ids),
        "entity_types": sorted(_get_entity_types_from_resource(resource=dataset)),
    }


def _build_db_rt_fingerprint_tdg(feed: Gtfsrealtimefeed) -> dict:
    return {
        "stable_id": getattr(feed, "stable_id", None),
        "feed_name": getattr(feed, "feed_name", None),
        "provider": getattr(feed, "provider", None),
        "producer_url": getattr(feed, "producer_url", None),
        "license_url": getattr(feed, "license_url", None),
        "static_refs": sorted({gf.stable_id for gf in feed.gtfs_feeds})
        if feed.gtfs_feeds
        else [],
        "entity_types": sorted({et.name for et in feed.entitytypes})
        if feed.entitytypes
        else [],
    }


# ---------------------------------------------------------------------------
# Per-dataset processing
# ---------------------------------------------------------------------------


def _process_tdg_dataset(
    db_session: Session,
    session_http: requests.Session,
    dataset: dict,
    processed_stable_ids: Optional[set] = None,
) -> Tuple[dict, List[Feed]]:
    """
    Process one TDG dataset:
      - create/update schedule GTFS feeds
      - create/update RT feeds linked to the schedule
      - attach locations
      - use diffing to avoid unnecessary DB writes
    Returns:
      (deltas_dict, feeds_to_publish)
    """
    created_gtfs = 0
    updated_gtfs = 0
    created_rt = 0
    processed = 0

    feeds_to_publish: List[Feed] = []

    dataset_id = dataset.get("id")
    dataset_title = dataset.get("title")

    logger.info("Processing TDG dataset id=%s title=%s", dataset_id, dataset_title)

    resources = sorted(
        dataset.get("resources", []) or [],
        key=lambda r: 0 if r.get("format") == GTFS_FORMAT else 1,
    )

    # Map of dataset_id -> list of static gtfs feed
    static_feeds_by_dataset_id: Dict[str, List[Gtfsfeed]] = {}

    # Precompute locations once per dataset
    locations = _get_tdg_locations(db_session, dataset)

    for resource in resources:
        res_format = resource.get("format")
        if res_format not in (GTFS_FORMAT, GTFS_RT_FORMAT):
            continue

        res_id = str(resource.get("id") or "")
        res_title = resource.get("title")
        res_url = resource.get("url")

        if not res_url or not res_id:
            logger.info(
                "Skipping resource without url or id (format=%s title=%s)",
                res_format,
                res_title,
            )
            continue

        # ---- STATIC GTFS ----
        if res_format == GTFS_FORMAT:
            stable_id = f"tdg-{res_id}"
            processed_stable_ids.add(stable_id)
            gtfs_feed, is_new = get_or_create_feed(
                db_session,
                Gtfsfeed,
                stable_id,
                "gtfs",
                official_notes="Imported from Transport.data.gouv.fr as official feed.",
            )

            if not is_new:
                api_fp = _build_api_schedule_fingerprint_tdg(
                    dataset=dataset, resource=resource, producer_url=res_url
                )
                db_fp = _build_db_schedule_fingerprint_tdg(gtfs_feed)
                if db_fp == api_fp:
                    logger.info(
                        "No change detected; skipping TDG GTFS feed stable_id=%s",
                        stable_id,
                    )
                    processed += 1
                    if dataset_id not in static_feeds_by_dataset_id:
                        static_feeds_by_dataset_id[dataset_id] = []
                    static_feeds_by_dataset_id[dataset_id].append(gtfs_feed)
                    continue

            # Requirement: if GTFS url returns CSV, skip it (listing, not feed).
            status_code, content_type, detected_format = _probe_head_format(
                session_http, res_url
            )
            logger.debug(
                "TDG probe: url=%s status=%s ctype=%s detected=%s",
                res_url,
                status_code,
                content_type,
                detected_format,
            )

            if detected_format == "csv":
                logger.info(
                    "Skipping GTFS resource id=%s because it returns CSV (url=%s)",
                    res_id,
                    res_url,
                )
                continue

            # Apply changes
            _update_common_tdg_fields(
                gtfs_feed, dataset, resource, res_url, locations, db_session
            )
            _ensure_tdg_external_id(gtfs_feed, res_id)

            if dataset_id not in static_feeds_by_dataset_id:
                static_feeds_by_dataset_id[dataset_id] = []
            static_feeds_by_dataset_id[dataset_id].append(gtfs_feed)

            if is_new:
                created_gtfs += 1
                feeds_to_publish.append(gtfs_feed)
                logger.info("Created TDG GTFS feed stable_id=%s", stable_id)
            else:
                updated_gtfs += 1
                logger.info("Updated TDG GTFS feed stable_id=%s", stable_id)

            processed += 1

        # ---- GTFS-RT ----
        elif res_format == GTFS_RT_FORMAT:
            # Pick the first static GTFS feed created for this dataset as reference
            static_gtfs_feeds = (
                static_feeds_by_dataset_id[dataset_id]
                if dataset_id in static_feeds_by_dataset_id
                else None
            )

            rt_stable_id = f"tdg-{res_id}"
            processed_stable_ids.add(rt_stable_id)
            rt_feed, is_new_rt = get_or_create_feed(
                db_session, Gtfsrealtimefeed, rt_stable_id, "gtfs_rt"
            )

            if not is_new_rt:
                api_rt_fp = _build_api_rt_fingerprint_tdg(
                    dataset=dataset,
                    producer_url=res_url,
                    static_gtfs_stable_ids=[
                        static_gtfs_feed.stable_id
                        for static_gtfs_feed in static_gtfs_feeds
                    ],
                    rt_stable_id=rt_stable_id,
                )
                db_rt_fp = _build_db_rt_fingerprint_tdg(rt_feed)
                if db_rt_fp == api_rt_fp:
                    logger.info(
                        "No change detected; skipping TDG RT feed stable_id=%s",
                        rt_stable_id,
                    )
                    processed += 1
                    continue

            # Apply changes
            _update_common_tdg_fields(
                rt_feed, dataset, resource, res_url, locations, db_session
            )
            _ensure_tdg_external_id(rt_feed, res_id)

            # Link RT → schedule
            rt_feed.gtfs_feeds = static_gtfs_feeds

            # Add entity types
            entity_types = _get_entity_types_from_resource(resource)
            rt_feed.entitytypes = [
                get_or_create_entity_type(db_session, et) for et in entity_types
            ]

            if is_new_rt:
                created_rt += 1
                logger.info(
                    "Created TDG RT feed stable_id=%s linked_to=%s",
                    rt_stable_id,
                    ", ".join(
                        [
                            static_gtfs_feed.stable_id
                            for static_gtfs_feed in static_gtfs_feeds
                        ]
                    ),
                )
            else:
                logger.info(
                    "Updated TDG RT feed stable_id=%s linked_to=%s",
                    rt_stable_id,
                    ", ".join(
                        [
                            static_gtfs_feed.stable_id
                            for static_gtfs_feed in static_gtfs_feeds
                        ]
                    ),
                )

            processed += 1

    deltas = {
        "created_gtfs": created_gtfs,
        "updated_gtfs": updated_gtfs,
        "created_rt": created_rt,
        "processed": processed,
    }
    return deltas, feeds_to_publish


# ---------------------------------------------------------------------------
# Orchestrator & handler
# ---------------------------------------------------------------------------


@with_db_session
def _import_tdg(db_session: Session, dry_run: bool = True) -> dict:
    """
    Orchestrate TDG import:
      - fetch list
      - iterate over datasets
      - batch commit + trigger dataset downloads for new schedule feeds
      - use diffing to avoid unnecessary DB writes
    """
    logger.info("Starting TDG import dry_run=%s", dry_run)
    session_http = requests.Session()

    try:
        datasets = _fetch_tdg_datasets(session_http)
    except Exception as e:
        logger.exception("Exception during TDG datasets request")
        return {
            "message": "Failed to fetch TDG datasets.",
            "error": str(e),
            "params": {"dry_run": dry_run},
            "created_gtfs": 0,
            "updated_gtfs": 0,
            "created_rt": 0,
            "total_processed_items": 0,
        }

    logger.info(
        "Commit batch size (env COMMIT_BATCH_SIZE)=%s",
        os.getenv("COMMIT_BATCH_SIZE", "5"),
    )
    commit_batch_size = int(os.getenv("COMMIT_BATCH_SIZE", "5"))

    created_gtfs = updated_gtfs = created_rt = total_processed = 0
    feeds_to_publish: List[Feed] = []
    processed_stable_ids = set()
    for idx, dataset in enumerate(datasets, start=1):
        try:
            deltas, new_feeds = _process_tdg_dataset(
                db_session,
                session_http,
                dataset,
                processed_stable_ids=processed_stable_ids,
            )

            created_gtfs += deltas["created_gtfs"]
            updated_gtfs += deltas["updated_gtfs"]
            created_rt += deltas["created_rt"]
            total_processed += deltas["processed"]

            if not dry_run:
                feeds_to_publish.extend(new_feeds)

            if (
                not dry_run
                and total_processed
                and total_processed % commit_batch_size == 0
            ):
                logger.info("Committing batch at total_processed=%d", total_processed)
                commit_changes(db_session, feeds_to_publish, total_processed)
                feeds_to_publish = []

        except Exception as e:
            logger.exception("Exception processing TDG dataset at index=%d: %s", idx, e)
            continue

    if not dry_run:
        # Deprecate TDG feeds not seen in this import
        _deprecate_stale_feeds(db_session, processed_stable_ids)
        # Last commit for remaining feeds
        commit_changes(db_session, feeds_to_publish, total_processed)

    message = (
        "Dry run: no DB writes performed."
        if dry_run
        else "TDG import executed successfully."
    )
    summary = {
        "message": message,
        "created_gtfs": created_gtfs,
        "updated_gtfs": updated_gtfs,
        "created_rt": created_rt,
        "total_processed_items": total_processed,
        "params": {"dry_run": dry_run},
    }
    logger.info("TDG import summary: %s", summary)
    return summary


def commit_changes(
    db_session: Session, feeds_to_publish: List[Feed], total_processed: int
):
    """
    Commit DB changes and trigger dataset downloads for new feeds.
    Reused pattern from JBDA.
    """
    try:
        logger.info("Commit after processing items (count=%d)", total_processed)
        db_session.commit()
        execution_id = str(uuid.uuid4())
        if os.getenv("ENV", "").lower() == "local":
            return
        for feed in feeds_to_publish:
            trigger_dataset_download(feed, execution_id)
    except IntegrityError:
        db_session.rollback()
        logger.exception("Commit failed with IntegrityError; rolled back")


def import_tdg_handler(payload: Optional[dict] = None) -> dict:
    """
    Cloud Function entrypoint wrapper.

    Payload: {"dry_run": bool} (default True)
    """
    payload = payload or {}
    logger.info("import_tdg_handler called with payload=%s", payload)

    dry_run_raw = payload.get("dry_run", True)
    dry_run = (
        dry_run_raw
        if isinstance(dry_run_raw, bool)
        else str(dry_run_raw).lower() == "true"
    )
    logger.info("Parsed dry_run=%s (raw=%s)", dry_run, dry_run_raw)

    result = _import_tdg(dry_run=dry_run)
    logger.info(
        "import_tdg_handler summary: %s",
        {
            k: result.get(k)
            for k in (
                "message",
                "created_gtfs",
                "updated_gtfs",
                "created_rt",
                "total_processed_items",
            )
        },
    )
    return result
