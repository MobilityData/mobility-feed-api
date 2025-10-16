import json
import logging
import os
from typing import List, Dict, Tuple

import flask
import pycountry
from google.cloud import tasks_v2
from sqlalchemy.orm.session import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsdataset,
    Location,
    Gtfsfile,
)
from shared.helpers.logger import init_logger
from shared.helpers.utils import create_http_task
from sqlalchemy.orm import selectinload


init_logger()


@with_db_session
def get_feeds_data(
    country_codes: List[str], include_only_unprocessed: bool, db_session: Session
) -> List[Dict]:
    """Get the feeds data for the given country codes. In case no country codes are provided, fetch feeds for all
    countries."""
    query = (
        db_session.query(Gtfsdataset)
        .join(Gtfsfeed, Gtfsfeed.latest_dataset_id == Gtfsdataset.id)
        .filter(Gtfsdataset.feed.has(Gtfsfeed.status != "deprecated"))
        .filter(Gtfsdataset.gtfsfiles.any(Gtfsfile.file_name == "stops.txt"))
        .options(selectinload(Gtfsdataset.feed), selectinload(Gtfsdataset.gtfsfiles))
    )

    if country_codes:
        query = query.filter(
            Gtfsdataset.feed.has(
                Gtfsfeed.locations.any(Location.country_code.in_(country_codes))
            )
        )

    if include_only_unprocessed:
        query = query.filter(
            Gtfsdataset.feed.has(~Gtfsfeed.feedlocationgrouppoints.any())
        )

    results = query.populate_existing().all()

    data = [
        {
            "stable_id": ds.feed.stable_id,
            "dataset_id": ds.stable_id,
            "stops_url": next(
                (f.hosted_url for f in ds.gtfsfiles if f.file_name == "stops.txt"),
                None,
            ),
        }
        for ds in results
    ]
    return [d for d in data if d["stops_url"]]


def parse_request_parameters(request: flask.Request) -> Tuple[List[str], bool]:
    """Parse the request parameters to get the country codes and whether to include only unprocessed feeds."""
    json_request = request.get_json()
    country_codes = json_request.get("country_codes", "").split(",")
    country_codes = [code.strip().upper() for code in country_codes if code]

    # Validate country codes
    for country_code in country_codes:
        if not pycountry.countries.get(alpha_2=country_code):
            raise ValueError(f"Invalid country code: {country_code}")
    include_only_unprocessed = (
        json_request.get("include_only_unprocessed", True) is True
    )
    return country_codes, include_only_unprocessed


def reverse_geolocation_batch(request: flask.Request) -> Tuple[str, int]:
    """Batch function to trigger reverse geolocation for feeds."""
    try:
        country_codes, include_only_unprocessed = parse_request_parameters(request)
        feeds_data = get_feeds_data(country_codes, include_only_unprocessed)
        logging.info("Valid feeds with latest dataset: %s", len(feeds_data))

        for feed in feeds_data:
            create_http_processor_task(
                stable_id=feed["stable_id"],
                dataset_id=feed["dataset_id"],
                stops_url=feed["stops_url"],
            )
        return f"Batch function triggered for {len(feeds_data)} feeds.", 200
    except Exception as e:
        logging.error("Execution error: %s", e)
        return "Error while fetching feeds.", 500


def create_http_processor_task(
    stable_id: str,
    dataset_id: str,
    stops_url: str,
) -> None:
    """
    Create a task to process a group of points.
    """
    client = tasks_v2.CloudTasksClient()
    body = json.dumps(
        {"stable_id": stable_id, "stops_url": stops_url, "dataset_id": dataset_id}
    ).encode()
    queue_name = os.getenv("QUEUE_NAME")
    project_id = os.getenv("PROJECT_ID")
    gcp_region = os.getenv("GCP_REGION")

    create_http_task(
        client,
        body,
        f"https://{gcp_region}-{project_id}.cloudfunctions.net/reverse-geolocation-processor",
        project_id,
        gcp_region,
        queue_name,
    )
