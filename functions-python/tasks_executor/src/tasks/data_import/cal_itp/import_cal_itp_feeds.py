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
import json
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

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
from shared.common.gcp_utils import create_web_revalidation_task
from shared.helpers.pub_sub import trigger_dataset_download
from tasks.data_import.data_import_utils import (
    get_or_create_feed,
    get_or_create_entity_type,
    get_license,
)

logger = logging.getLogger(__name__)

_LOG_FILE_PATH = Path("/tmp/cal_itp_import_log")
_LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
_file_handler = logging.FileHandler(_LOG_FILE_PATH, encoding="utf-8")
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
)
logger.addHandler(_file_handler)

CAL_ITP_BASE = "https://data.ca.gov/api/3/action"
CAL_ITP_SQL_QUERY_URL = f"{CAL_ITP_BASE}/datastore_search_sql?sql="
REQUEST_TIMEOUT_S = 60

GTFS_SCHEDULE = "gtfs"
GTFS_REALTIME = "gtfs_rt"

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

CKAN_DATASET_IDS = {
    "gtfs_datasets": "e4ca5bd4-e9ce-40aa-a58a-3a6d78b042bd",
    "services": "dbacfa9f-2148-454c-a08f-a77233f2b8c0",
    "provider_gtfs_data": "ebe116fb-b9da-4fee-a0c5-497c9d6d61d7",
    "organizations": "677e1271-fea5-4c21-92fa-59eb336fde94"
}

ENTITY_TYPES_MAP = {
    "trip_updates": "tu",
    "vehicle_positions": "vp",
    "service_alerts": "sa",
}

CKAN_QUERY_TEMPLATE_PATH = Path(__file__).with_name("ckan_query.sql")

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class InvalidCalItpFeedError(Exception):
    """Raised when a Cal-ITP dataset/resource is missing required fields for a valid feed."""


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _get_license_url(license_id: Optional[str]) -> Optional[str]:
    """
    Map Cal-ITP license ID to URL if known.
    """
    if not license_id:
        return None
    return LICENSE_URL_MAP.get(license_id.strip().lower(), {}).get("url")


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
    Extract entity types from Cal-ITP resource `entity_type` field.
    """
    features = resource.get("entity_type", []) or []
    entity_types = []
    for feature in features:
        if isinstance(feature, str) and feature.lower() in ENTITY_TYPES_MAP:
            entity_types.append(ENTITY_TYPES_MAP.get(feature.lower()))
    return entity_types


def _fetch_cal_itp_datasets(session_http: requests.Session) -> List[dict]:
    """
    Fetch Cal-ITP datasets for GTFS import. No headers or auth needed for Cal-ITP CKAN API
    """
    logger.info("Fetching Cal-ITP datasets using %s", CAL_ITP_SQL_QUERY_URL)
    sql_query = CKAN_QUERY_TEMPLATE_PATH.read_text(encoding="utf-8").format(
        gtfs_dataset=CKAN_DATASET_IDS.get("gtfs_datasets", "gtfs_dataset"),
        services=CKAN_DATASET_IDS.get("services", "services"),
        provider_gtfs_data=CKAN_DATASET_IDS.get("provider_gtfs_data", "provider_gtfs_data"),
        organizations=CKAN_DATASET_IDS.get("organizations", "organizations")
    )
    encoded_sql = requests.utils.quote(sql_query)
    logger.debug("Rendered Cal-ITP CKAN SQL query: %s", encoded_sql)
    endpoint = f"{CAL_ITP_SQL_QUERY_URL}{encoded_sql}"
    res = session_http.get(endpoint, timeout=REQUEST_TIMEOUT_S, headers={})
    res.raise_for_status()
    records = res.json()['result']['records']
    if isinstance(records, list):
        return records
    return records or []


# ---------------------------------------------------------------------------
# Record filtering
# ---------------------------------------------------------------------------

BAY_AREA_511_MARKER = "Bay Area 511 Regional"

REGIONAL_FEED_TYPE_PRIORITY = [
    "Regional Precursor Feed",
    "Regional Subfeed",
    "Combined Regional Feed",
]

_DATASET_NAME_COLUMNS = [
    "schedule_gtfs_dataset_name",
    "service_alerts_gtfs_dataset_name",
    "trip_updates_gtfs_dataset_name",
    "vehicle_positions_gtfs_dataset_name",
]


def _is_bay_area_511(record: dict) -> bool:
    """Return True if any dataset-name column contains the Bay Area 511 marker."""
    for col in _DATASET_NAME_COLUMNS:
        val = record.get(col)
        if val and BAY_AREA_511_MARKER in str(val):
            return True
    return False


def _is_customer_facing(record: dict) -> bool:
    return str(record.get("gtfs_service_data_customer_facing", "")).lower() in (
        "true",
        "yes",
        "1",
    )


def _filter_cal_itp_records(records: List[dict]) -> List[dict]:
    """
    Apply two filtering strategies depending on service context:

    * If any of schedule_gtfs_dataset_name, service_alerts_gtfs_dataset_name,
      trip_updates_gtfs_dataset_name or vehicle_positions_gtfs_dataset_name
      contains "Bay Area 511 Regional", apply regional feed type priority:
        1. Regional Precursor Feed (if exists)
        2. Regional Subfeed (if exists)
        3. Combined Regional Feed (if exists)
        If none of the three priority types exist, keep all records as a fallback.

      Else keep only records where gtfs_service_data_customer_facing is truthy.
    """
    groups: Dict[str, List[dict]] = defaultdict(list)
    for rec in records:
        groups[rec.get("service_source_record_id", "")].append(rec)

    filtered: List[dict] = []
    for service_id, group in groups.items():
        is_bay_area = any(_is_bay_area_511(r) for r in group)

        if is_bay_area:
            types_present = {
                str(r.get("regional_feed_type", "") or "") for r in group
            }
            selected_type = None
            for ptype in REGIONAL_FEED_TYPE_PRIORITY:
                if ptype in types_present:
                    selected_type = ptype
                    break

            if selected_type is not None:
                kept = [
                    r for r in group
                    if str(r.get("regional_feed_type", "") or "") == selected_type
                ]
                logger.debug(
                    "Bay Area 511 filter: service_id=%s kept %d/%d records "
                    "(regional_feed_type=%s)",
                    service_id,
                    len(kept),
                    len(group),
                    selected_type,
                )
                filtered.extend(kept)
            else:
                logger.debug(
                    "Bay Area 511 filter: service_id=%s no priority type found, "
                    "keeping all %d records as fallback",
                    service_id,
                    len(group),
                )
                filtered.extend(group)
        else:
            kept = [r for r in group if _is_customer_facing(r)]
            logger.debug(
                "Customer-facing filter: service_id=%s kept %d/%d records",
                service_id,
                len(kept),
                len(group),
            )
            filtered.extend(kept)

    logger.debug(
        "Record filtering complete: %d -> %d records", len(records), len(filtered)
    )
    return filtered


# ---------------------------------------------------------------------------
# Location helpers
# ---------------------------------------------------------------------------


def _get_cal_itp_locations(db_session: Session, dataset: dict) -> List[Any]:
    """
    Map Cal-ITP `organization.caltrans_district_name` entries to Location rows.

    organization records look like:
      {
        "caltrans_district_name": "San Bernardino"
      }

    Rules:
      - Hardcode country to USA
      - Hardcode state to California
      - Use city name from caltrans_district_name if it exists
    """
    district_name = dataset.get("caltrans_district_name", []) or []
    country_name = "United States"
    state_province = "California"

    locations: List[Any] = []

    loc = create_or_get_location(
        db_session,
        country=country_name,
        state_province=state_province,
        city_name=district_name,
    )
    locations.append(loc)

    return locations


# ---------------------------------------------------------------------------
# Feed helpers
# ---------------------------------------------------------------------------

TFeed = TypeVar("TFeed", bound=Feed)


def _validate_required_cal_itp_fields(
    resource: dict
) -> Tuple[str, str, str, str, str, str]:
    """
    Validate required Cal-ITP fields BEFORE creating/upserting DB rows.
    This avoids persisting invalid feeds when the resource is missing key data.

    Returns service_id, res_format, res_id, res_name, res_url, feed_type
    """
    service_id = resource.get("service_source_record_id")
    res_format = resource.get("format")
    if res_format == GTFS_SCHEDULE:
        feed_type = 'schedule'
        try:
            res_id = resource.get("schedule_source_record_id")
            res_name = resource.get("schedule_gtfs_dataset_name")
            res_url = resource.get("schedule_dataset_url")
        except Exception as e:
            raise InvalidCalItpFeedError(e)
    elif res_format == GTFS_REALTIME:
        feed_type = next(
            (t for t in ENTITY_TYPES_MAP if resource.get(f"{t}_gtfs_dataset_name")),
            None,
        )
        if feed_type is None:
            raise InvalidCalItpFeedError("Cal-ITP RT resource has no recognised type in ENTITY_TYPES_MAP")
        try:
            res_id = resource.get(f"{feed_type}_source_record_id")
            res_name = resource.get(f"{feed_type}_gtfs_dataset_name")
            res_url = resource.get(f"{feed_type}_dataset_url")
        except Exception as e:
            raise InvalidCalItpFeedError(e)
    else:
        raise InvalidCalItpFeedError(f"Cal-ITP resource has unknown format: {res_format!r}")

    return service_id, res_format, res_id, res_name, res_url, feed_type


def _delete_and_recreate_feed_if_type_changed(
    db_session: Session,
    model_cls: Type[TFeed],
    stable_id: str,
    feed_type: str,
    **get_or_create_kwargs: Any,
) -> Tuple[TFeed, bool]:
    """
    If a Feed exists with the same stable_id but is a different data_type
    (e.g., GTFS-RT in DB but now Cal-ITP says it's GTFS), delete the old entity and
    recreate using the requested model class.

    Returns: (feed, is_new)
      - is_new True when created (including after deletion/recreate)
      - is_new False when existing row already matches feed_type
    """
    existing: Optional[Feed] = (
        db_session.query(Feed).filter(Feed.stable_id == stable_id).one_or_none()
    )

    if existing is not None and existing.data_type != feed_type:
        logger.info(
            "Cal-ITP feed type changed for stable_id=%s: db_data_type=%s -> new_data_type=%s. Deleting and recreating.",
            stable_id,
            getattr(existing, "data_type", None),
            feed_type,
        )
        db_session.delete(existing)
        # flush so the new insert doesn't collide on stable_id unique constraint
        db_session.flush()

    feed, is_new = get_or_create_feed(
        db_session,
        model_cls,
        stable_id,
        feed_type,
        **get_or_create_kwargs,
    )
    return feed, is_new


def _deprecate_stale_feeds(db_session, processed_stable_ids):
    """
    Deprecate Cal-ITP feeds not seen in this import run.
    """
    logger.info("Deprecating stale Cal-ITP feeds not in processed_stable_ids")
    cal_itp_feeds = (
        db_session.query(Feed)
        .filter(Feed.stable_id.like("cal_itp-%"))
        .filter(~Feed.stable_id.in_(processed_stable_ids))
        .all()
    )
    logger.info("Found %d cal_itp_feeds stale stable_ids", len(cal_itp_feeds))
    deprecated_count = 0
    for feed in cal_itp_feeds:
        if feed.status != "deprecated":
            feed.status = "deprecated"
            deprecated_count += 1
            logger.info("Deprecated stale Cal-ITP feed stable_id=%s", feed.stable_id)

    logger.info("Total deprecated stale Cal-ITP feeds: %d", deprecated_count)


def _ensure_cal_itp_external_id(feed: Feed, resource_id: str) -> None:
    """
    Ensure that an Externalid(source='cal_itp', associated_id=<resource_id>) exists.
    """
    if not resource_id:
        return

    has_cal_itp = any(
        (ei.source == "cal_itp" and ei.associated_id == resource_id)
        for ei in getattr(feed, "externalids", [])
    )
    if not has_cal_itp:
        feed.externalids.append(Externalid(associated_id=resource_id, source="cal_itp"))
        logger.debug("Appended missing Cal-ITP Externalid for %s", feed.stable_id)


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


def _update_common_cal_itp_fields(
    feed: Feed,
    resource: dict,
    res_name: str,
    producer_url: str,
    locations: List[Location],
    db_session: Session,
) -> None:
    """
    Update common fields for both schedule GTFS and RT from Cal-ITP dataset + resource.
    Assumes required fields were validated earlier.
    """
    feed.feed_name = res_name
    feed.provider = resource.get("organization_name")
    feed.producer_url = producer_url

    # to compute with validator?
    # feed.status = _compute_status_from_end_date(resource.get("metadata") or {})
    feed.operational_status = "published"

    # to follow up with Cal-ITP on license handling
    # feed.license_url = _get_license_url(resource.get("licence"))
    # feed_license = get_license(
    #     db_session, LICENSE_URL_MAP.get(resource.get("licence"), {}).get("id")
    # )
    # if feed_license:
    #     feed.license = feed_license

    # Use locations only if not already set
    if locations and (not feed.locations or len(feed.locations) == 0):
        feed.locations = locations

    logger.debug(
        "Updated Cal-ITP feed fields: stable_id=%s provider=%s operational_status=%s",
        feed.stable_id,
        feed.provider,
        feed.operational_status,
    )


# ---------------------------------------------------------------------------
# Fingerprints (for diffing)
# ---------------------------------------------------------------------------


def _build_api_schedule_fingerprint_cal_itp(
    resource: dict,
    producer_url: str,
    feed_name: str,
    stable_id: str,
) -> dict:
    return {
        "stable_id": stable_id,
        "feed_name": feed_name,
        "provider": resource.get("organization_name"),
        "producer_url": producer_url,
        # "license_url": _get_license_url(resource.get("licence")),
    }


def _build_db_schedule_fingerprint_cal_itp(feed: Gtfsfeed) -> dict:
    return {
        "stable_id": getattr(feed, "stable_id", None),
        "feed_name": getattr(feed, "feed_name", None),
        "provider": getattr(feed, "provider", None),
        "producer_url": getattr(feed, "producer_url", None),
        # "license_url": getattr(feed, "license_url", None),
    }


def _build_api_rt_fingerprint_cal_itp(
    resource: dict,
    producer_url: str,
    feed_name: str,
    static_gtfs_stable_ids: List[str],
    rt_stable_id: str,
) -> dict:
    return {
        "stable_id": rt_stable_id,
        "feed_name": feed_name,
        "provider": resource.get("organization_name"),
        "producer_url": producer_url,
        # "license_url": _get_license_url(dataset.get("licence")),
        "static_refs": sorted(static_gtfs_stable_ids),
        "entity_types": sorted(_get_entity_types_from_resource(resource=resource)),
    }


def _build_db_rt_fingerprint_cal_itp(feed: Gtfsrealtimefeed) -> dict:
    return {
        "stable_id": getattr(feed, "stable_id", None),
        "feed_name": getattr(feed, "feed_name", None),
        "provider": getattr(feed, "provider", None),
        "producer_url": getattr(feed, "producer_url", None),
        # "license_url": getattr(feed, "license_url", None),
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


def _process_cal_itp_dataset(
    db_session: Session,
    session_http: requests.Session,
    dataset: dict,
    processed_stable_ids: Optional[set] = None,
) -> Tuple[dict, List[Feed], List[str]]:
    """
    Process one Cal-ITP dataset:
      - validate required fields BEFORE creating/updating any DB rows
      - create/update schedule GTFS feeds
      - create/update RT feeds linked to the schedule
      - attach locations
      - use diffing to avoid unnecessary DB writes
      - if stable_id exists in DB but with wrong entity type, delete+recreate
    Returns:
      (deltas_dict, feeds_to_publish, changed_stable_ids)
    """
    created_gtfs = 0
    updated_gtfs = 0
    created_rt = 0
    processed = 0

    feeds_to_publish: List[Feed] = []

    _common_fields = {
        "service_name": dataset.get("service_name"),
        "service_source_record_id": dataset.get("service_source_record_id"),
        "organization_name": dataset.get("organization_name"),
        "organization_source_record_id": dataset.get("organization_source_record_id"),
        "caltrans_district_name": dataset.get("caltrans_district_name"),
    }

    _raw_resources = []
    if dataset.get("schedule_gtfs_dataset_name"):
        _raw_resources.append({
            **_common_fields,
            "format": GTFS_SCHEDULE,
            "schedule_source_record_id": dataset.get("schedule_source_record_id"),
            "schedule_gtfs_dataset_name": dataset.get("schedule_gtfs_dataset_name"),
            "schedule_dataset_url": dataset.get("schedule_dataset_url"),
        })
    for _rt_type in ENTITY_TYPES_MAP:
        if dataset.get(f"{_rt_type}_gtfs_dataset_name"):
            _raw_resources.append({
                **_common_fields,
                "format": GTFS_REALTIME,
                "entity_type":f"{_rt_type}",
                f"{_rt_type}_source_record_id": dataset.get(f"{_rt_type}_source_record_id"),
                f"{_rt_type}_gtfs_dataset_name": dataset.get(f"{_rt_type}_gtfs_dataset_name"),
                f"{_rt_type}_dataset_url": dataset.get(f"{_rt_type}_dataset_url"),
            })
    resources = sorted(
        _raw_resources,
        key=lambda r: 0 if r.get("schedule_gtfs_dataset_name") else 1,
    )

    schedule_feeds_by_service_id: Dict[str, List[Gtfsfeed]] = {}

    # Precompute locations once per dataset
    locations = _get_cal_itp_locations(db_session, dataset)

    for resource in resources:

        res_id = (
            str(resource.get("schedule_source_record_id") or "")
            if resource.get("format") == GTFS_SCHEDULE
            else str(resource.get(f"{next((t for t in ENTITY_TYPES_MAP if resource.get(f'{t}_gtfs_dataset_name')), None)}_source_record_id") or "")
        )

        # Validate required fields up-front (fixes: creating feeds before validation)
        try:
            service_id, res_format, res_id, res_name, res_url, feed_type = _validate_required_cal_itp_fields(resource)
            logger.info(
                "Validated Cal-ITP resource fields for resource_id=%s: format=%s name=%s url=%s",
                res_id,
                res_format,
                res_name,
                res_url,
            )

            # cal_itp-{service_source_record_id}-{feed_type}
            # where feed_type = [s, sa, tu, vp] (schedule, service_alerts, trip_updates, vehicle_positions)
            # and because service_source_record_id is stable
            feed_type_code = ENTITY_TYPES_MAP.get(feed_type, "s") # default with s for schedule feeds which are not an EntityType
            stable_id = f"cal_itp-{service_id}-{feed_type_code}"
            processed_stable_ids.add(stable_id)

        except InvalidCalItpFeedError as e:
            logger.warning(
                "Invalid Cal-ITP resource skipped (dataset_id=%s resource_id=%s): %s",
                service_id,
                res_id,
                e,
            )
            continue

        # SAVEPOINT per resource
        nested = db_session.begin_nested()
        try:
            # ---- STATIC GTFS ----
            if res_format == GTFS_SCHEDULE:
                # Requirement: if GTFS url returns non zip, skip it
                status_code, content_type, detected_format = _probe_head_format(
                    session_http, res_url
                )
                logger.debug(
                    "Cal-ITP probe: url=%s status=%s ctype=%s detected=%s",
                    res_url,
                    status_code,
                    content_type,
                    detected_format,
                )

                # if detected_format != "zip":
                #     logger.info(
                #         "Skipping GTFS resource id=%s because it does not return zip (url=%s)",
                #         res_id,
                #         res_url,
                #     )
                #     nested.rollback()
                #     continue

                gtfs_feed, new_feed = _delete_and_recreate_feed_if_type_changed(
                    db_session,
                    Gtfsfeed,
                    stable_id,
                    res_format,
                    # official_notes="Imported from Cal-ITP as official feed.",
                )

                if not new_feed:
                    api_fp = _build_api_schedule_fingerprint_cal_itp(
                        resource=resource,
                        producer_url=res_url,
                        feed_name=res_name,
                        stable_id=stable_id
                    )
                    db_fp = _build_db_schedule_fingerprint_cal_itp(gtfs_feed)
                    if db_fp == api_fp:
                        logger.info(
                            "No change detected; skipping Cal-ITP GTFS feed stable_id=%s",
                            stable_id,
                        )
                        processed += 1
                        schedule_feeds_by_service_id.setdefault(service_id, []).append(
                            gtfs_feed
                        )
                        nested.commit()
                        continue

                _update_common_cal_itp_fields(
                    feed=gtfs_feed,
                    resource=resource,
                    res_name=res_name,
                    producer_url=res_url,
                    locations=locations,
                    db_session=db_session
                )
                _ensure_cal_itp_external_id(gtfs_feed, res_id)

                schedule_feeds_by_service_id.setdefault(service_id, []).append(gtfs_feed)

                if new_feed:
                    created_gtfs += 1
                    feeds_to_publish.append(gtfs_feed)
                    logger.info("Created Cal-ITP GTFS feed stable_id=%s", stable_id)
                else:
                    updated_gtfs += 1
                    logger.info("Updated Cal-ITP GTFS feed stable_id=%s", stable_id)

                processed += 1
                nested.commit()
                continue

            # ---- GTFS-RT ----
            if res_format == GTFS_REALTIME:
                static_gtfs_feeds = schedule_feeds_by_service_id.get(service_id, [])

                rt_feed, new_rt = _delete_and_recreate_feed_if_type_changed(
                    db_session,
                    Gtfsrealtimefeed,
                    stable_id,
                    res_format,
                )

                if not new_rt:
                    api_rt_fp = _build_api_rt_fingerprint_cal_itp(
                        resource=resource,
                        producer_url=res_url,
                        feed_name=res_name,
                        static_gtfs_stable_ids=[
                            static_gtfs_feed.stable_id
                            for static_gtfs_feed in static_gtfs_feeds
                        ],
                        rt_stable_id=stable_id,
                    )
                    db_rt_fp = _build_db_rt_fingerprint_cal_itp(rt_feed)
                    if db_rt_fp == api_rt_fp:
                        logger.info(
                            "No change detected; skipping Cal-ITP RT feed stable_id=%s",
                            stable_id,
                        )
                        processed += 1
                        nested.commit()
                        continue

                _update_common_cal_itp_fields(
                    feed=rt_feed,
                    resource=resource,
                    res_name=res_name,
                    producer_url=res_url,
                    locations=locations,
                    db_session=db_session
                )
                _ensure_cal_itp_external_id(rt_feed, res_id)

                # Link RT → schedule (can be empty if schedule missing)
                rt_feed.gtfs_feeds = static_gtfs_feeds

                # Add entity types
                entity_types = _get_entity_types_from_resource(resource=resource)
                rt_feed.entitytypes = [
                    get_or_create_entity_type(db_session, et) for et in entity_types
                ]

                if new_rt:
                    created_rt += 1
                    logger.info(
                        "Created Cal-ITP RT feed stable_id=%s linked_to=%s",
                        stable_id,
                        ", ".join([f.stable_id for f in static_gtfs_feeds]),
                    )
                else:
                    logger.info(
                        "Updated Cal-ITP RT feed stable_id=%s linked_to=%s",
                        stable_id,
                        ", ".join([f.stable_id for f in static_gtfs_feeds]),
                    )

                processed += 1
                nested.commit()
                continue

        except IntegrityError:
            # rollback nested transaction explicitly
            nested.rollback()
            logger.exception(
                "IntegrityError while processing Cal-ITP resource (dataset_id=%s resource_id=%s). Skipping.",
                service_id,
                res_id,
            )
            continue
        except Exception as e:
            # Any unexpected exception: rollback savepoint for this resource
            nested.rollback()
            logger.exception(
                "Exception while processing Cal-ITP resource (dataset_id=%s resource_id=%s): %s",
                service_id,
                res_id,
                e,
            )
            continue

    # Collect stable IDs of changed feeds for web app cache revalidation
    changed_stable_ids = (
        list(processed_stable_ids)
        if (created_gtfs or updated_gtfs or created_rt)
        else []
    )

    deltas = {
        "created_gtfs": created_gtfs,
        "updated_gtfs": updated_gtfs,
        "created_rt": created_rt,
        "processed": processed,
    }
    return deltas, feeds_to_publish, changed_stable_ids


# ---------------------------------------------------------------------------
# Orchestrator & handler
# ---------------------------------------------------------------------------


@with_db_session
def _import_cal_itp(db_session: Session, dry_run: bool = True) -> dict:
    """
    Orchestrate Cal-ITP import:
      - fetch list
      - iterate over datasets
      - batch commit + trigger dataset downloads for new schedule feeds
      - use diffing to avoid unnecessary DB writes
      - delete/recreate entity if stable_id flips GTFS <-> GTFS-RT
    """
    logger.info("Starting Cal-ITP import dry_run=%s", dry_run)
    session_http = requests.Session()

    try:
        datasets = _fetch_cal_itp_datasets(session_http)
        logger.info("Fetched %d Cal-ITP datasets", len(datasets))
        datasets = _filter_cal_itp_records(datasets)
    except Exception as e:
        logger.exception("Exception during Cal-ITP datasets request")
        return {
            "message": "Failed to fetch Cal-ITP datasets.",
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
    changed_feed_stable_ids: List[str] = []
    processed_stable_ids = set()

    for idx, dataset in enumerate(datasets, start=1):
        previous_total_processed = total_processed
        logger.info("Processing dataset %d/%d: service_id=%s service_name=%s",
            idx, len(datasets), dataset.get("service_source_record_id"), dataset.get("service_name")
        )
        try:
            deltas, new_feeds, changed_ids = _process_cal_itp_dataset(
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
                changed_feed_stable_ids.extend(changed_ids)

            if (
                not dry_run
                and total_processed
                and previous_total_processed
                and total_processed // commit_batch_size
                > previous_total_processed // commit_batch_size
            ):
                logger.info("Committing batch at total_processed=%d", total_processed)
                commit_changes(
                    db_session,
                    feeds_to_publish,
                    total_processed,
                    changed_feed_stable_ids,
                )
                feeds_to_publish = []
                changed_feed_stable_ids = []

        except Exception as e:
            logger.exception("Exception processing Cal-ITP dataset at index=%d: %s", idx, e)
            continue

    if dry_run:
        db_session.rollback()
        logger.info("Dry run: rolled back all pending DB changes.")
    else:
        _deprecate_stale_feeds(db_session, processed_stable_ids)
        commit_changes(
            db_session, feeds_to_publish, total_processed, changed_feed_stable_ids
        )

    message = (
        "Dry run: no DB writes performed."
        if dry_run
        else "Cal-ITP import executed successfully."
    )
    summary = {
        "message": message,
        "created_gtfs": created_gtfs,
        "updated_gtfs": updated_gtfs,
        "created_rt": created_rt,
        "total_processed_items": total_processed,
        "params": {"dry_run": dry_run},
    }
    logger.info("Cal-ITP import summary: %s", summary)
    return summary


def commit_changes(
    db_session: Session,
    feeds_to_publish: List[Feed],
    total_processed: int,
    changed_feed_stable_ids: List[str] | None = None,
):
    """
    Commit DB changes, trigger dataset downloads for new feeds,
    and trigger web app cache revalidation for changed feeds.
    """
    try:
        logger.info("Commit after processing items (count=%d)", total_processed)
        db_session.commit()
        execution_id = str(uuid.uuid4())
        if os.getenv("ENV", "").lower() == "local":
            return
        for feed in feeds_to_publish:
            trigger_dataset_download(feed, execution_id)
        if changed_feed_stable_ids:
            try:
                create_web_revalidation_task(changed_feed_stable_ids)
            except Exception as e:
                logger.warning("Failed to enqueue revalidation tasks: %s", e)
    except IntegrityError:
        db_session.rollback()
        logger.exception("Commit failed with IntegrityError; rolled back")


def import_cal_itp_handler(payload: Optional[dict] = None) -> dict:
    """
    Cloud Function entrypoint wrapper.

    Payload: {"dry_run": bool} (default True)
    """
    payload = payload or {}
    logger.info("import_cal_itp_handler called with payload=%s", payload)

    dry_run_raw = payload.get("dry_run", True)
    dry_run = (
        dry_run_raw
        if isinstance(dry_run_raw, bool)
        else str(dry_run_raw).lower() == "true"
    )
    logger.info("Parsed dry_run=%s (raw=%s)", dry_run, dry_run_raw)

    result = _import_cal_itp(dry_run=dry_run)
    logger.info(
        "import_cal_itp_handler summary: %s",
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
