#
#   MobilityData 2025
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

import json
import logging
import os
import re
from typing import Any, Dict, List

from sqlalchemy import select, func

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed
from shared.helpers.locations import round_geojson_coords
from shared.helpers.runtime_metrics import track_metrics

GEOLOCATION_FILENAME = "geolocation.geojson"


def _remove_osm_ids_from_properties(props: Dict[str, Any] | None):
    """Remove OSM identifier-like properties from a feature's properties in-place."""
    if not props or not isinstance(props, dict):
        return
    keys_to_remove = []
    for k, v in list(props.items()):
        lk = k.lower()
        if "osm" in lk or lk == "@id":
            keys_to_remove.append(k)
        elif lk == "id":
            if isinstance(v, str) and re.search(
                r"\b(node|way|relation)\b|/", v, re.IGNORECASE
            ):
                keys_to_remove.append(k)
    for k in keys_to_remove:
        props.pop(k, None)


def query_unprocessed_feeds(limit, db_session):
    """
    Query Gtfsfeed entries that have not been processed yet, geolocation_file_created_date is null.
    """
    feeds = (
        db_session.query(Gtfsfeed)
        .filter(Gtfsfeed.geolocation_file_created_date.is_(None))
        .limit(limit)
        .all()
    )
    return feeds


@track_metrics(metrics=("time", "memory", "cpu"))
def _upload_file(bucket, geojson):
    processed_blob = bucket.blob("geolocation.geojson")
    processed_blob.upload_from_string(
        json.dumps(geojson, ensure_ascii=False),
        content_type="application/geo+json",
    )


@track_metrics(metrics=("time", "memory", "cpu"))
def _update_feed_info(feed: Gtfsfeed, timestamp):
    feed.geolocation_file_created_date = timestamp
    # find the most recent dataset with bounding box and set the id
    if feed.gtfsdatasets and any(d.bounding_box for d in feed.gtfsdatasets):
        latest_with_bbox = max(
            (d for d in feed.gtfsdatasets if d.bounding_box),
            key=lambda d: d.downloaded_at or timestamp,
        )
        feed.geolocation_file_dataset_id = latest_with_bbox.id
    else:
        logging.info(
            "No GTFS datasets available with bounding box for feed %s", feed.id
        )


@track_metrics(metrics=("time", "memory", "cpu"))
def process_geojson(geopjson, precision):
    # Normalize GeoJSON structure to FeatureCollection-like list of features
    if isinstance(geopjson, dict) and geopjson.get("type") == "FeatureCollection":
        features = geopjson.get("features", [])
    elif isinstance(geopjson, dict) and geopjson.get("type") == "Feature":
        features = [geopjson]
    elif isinstance(geopjson, list):
        features = geopjson
    else:
        # Unknown structure, skip
        return
    # Apply rounding via shared helper and remove osm ids
    for f in features:
        if not isinstance(f, dict):
            continue
        geom = f.get("geometry")
        if geom:
            # round_geojson_coords returns a new geometry object
            try:
                f["geometry"] = round_geojson_coords(geom, precision=precision)
            except Exception as e:
                logging.warning("Error processing feature %s: %s", f.get("name"), e)
                return
        props = f.get("properties")
        _remove_osm_ids_from_properties(props)
    # If original was a FeatureCollection, update it; if single Feature, keep as-is; if list, use list
    if isinstance(geopjson, dict) and geopjson.get("type") == "FeatureCollection":
        geopjson["features"] = features
    elif isinstance(geopjson, dict) and geopjson.get("type") == "Feature":
        geopjson = features[0] if features else geopjson
    else:
        geopjson = features
    return geopjson


@with_db_session
def update_geojson_files_precision_handler(
    payload: Dict[str, Any], db_session
) -> Dict[str, Any]:
    """
    Update GeoJSON files in GCS to reduce coordinate precision and remove map ids.

    Payload keys:
      - dry_run (bool) default True
      - precision (int) default 5
      - limit (int)

    """
    # Import GCS client at runtime to avoid dev environment import issues
    try:
        from google.cloud import storage
    except Exception as e:
        raise RuntimeError("google-cloud-storage is required at runtime: %s" % e)
    bucket_name = payload.get("bucket_name") or os.getenv("DATASETS_BUCKET_NAME")
    if not bucket_name:
        raise ValueError(
            "bucket_name must be provided in payload or set in GEOJSON_BUCKET env"
        )

    dry_run = payload.get("dry_run", True)
    precision = int(payload.get("precision", 5))
    limit = int(payload.get("limit", None))
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    errors: List[Dict[str, str]] = []
    processed = 0

    feeds: [Gtfsfeed] = query_unprocessed_feeds(limit, db_session)
    logging.info("Found %s feeds", len(feeds))
    timestamp = db_session.execute(select(func.current_timestamp())).scalar()
    for feed in feeds:
        try:
            if processed % 100 == 0:
                logging.info("Processed %s/%s", processed, len(feeds))
                db_session.commit()
            file = storage.Blob(
                bucket=bucket, name=f"{feed.stable_id}/{GEOLOCATION_FILENAME}"
            )
            if not file.exists():
                logging.info("File does not exist: %s", file.name)
                continue
            logging.info("Processing file: %s", file.name)
            text = file.download_as_text()
            geojson = json.loads(text)

            geojson = process_geojson(geojson, precision)
            if not geojson:
                logging.warning("No valid GeoJSON features found in %s", file.name)
                errors.append(feed.stable_id)
                continue

            # Optionally upload processed geojson
            if not dry_run:
                _upload_file(bucket, geojson)
                _update_feed_info(feed, timestamp)

            processed += 1
        except Exception as e:
            logging.exception("Error processing feed %s: %s", feed.stable_id, e)
            errors.append(feed.stable_id)
    if not dry_run and processed > 0:
        db_session.commit()
    summary = {
        "total_processed_files": processed,
        "errors": errors,
        "not_found_file": len(feeds) - processed - len(errors),
        "params": {
            "dry_run": dry_run,
            "precision": precision,
            "limit": limit,
        },
    }
    logging.info("update_geojson_files_handler result: %s", summary)
    return summary
