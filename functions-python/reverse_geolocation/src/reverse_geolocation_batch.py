import logging
import os
from typing import List, Dict, Tuple

import flask
import pycountry
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm.session import Session

from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset, Location
from shared.database.database import with_db_session
from shared.helpers.logger import Logger
from shared.helpers.pub_sub import publish_messages


@with_db_session
def get_feeds_data(
    country_codes: List[str], include_only_unprocessed: bool, db_session: Session
) -> List[Dict]:
    """Get the feeds data for the given country codes. In case no country codes are provided, fetch feeds for all
    countries."""
    query = (
        db_session.query(Gtfsfeed)
        .join(Gtfsfeed.gtfsdatasets)
        .join(Gtfsfeed.locations)
        .options(contains_eager(Gtfsfeed.gtfsdatasets))
        .filter(Gtfsfeed.status != "deprecated")
        .filter(Gtfsdataset.latest)
    )
    if country_codes:
        logging.info("Getting feeds for country codes: %s", country_codes)
        query = query.filter(
            Gtfsfeed.locations.any(Location.country_code.in_(country_codes))
        )
    else:
        logging.warning("No country codes provided. Fetching feeds for all countries.")

    if include_only_unprocessed:
        logging.info("Filtering for unprocessed feeds.")
        query = query.filter(~Gtfsfeed.feedlocationgrouppoints.any())

    results = query.populate_existing().all()
    logging.info(f"Found {len(results)} feeds.")

    data = [
        {
            "stable_id": feed.stable_id,
            "dataset_id": feed.gtfsdatasets[0].stable_id,
            "url": feed.gtfsdatasets[0].hosted_url,
        }
        for feed in results
    ]
    return data


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
        Logger.init_logger()
        country_codes, include_only_unprocessed = parse_request_parameters(request)
        feeds_data = get_feeds_data(country_codes, include_only_unprocessed)
        logging.info("Valid feeds with latest dataset: %s", len(feeds_data))

        pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME", None)
        project_id = os.getenv("PROJECT_ID")

        logging.info("Publishing to topic: %s", pubsub_topic_name)
        publish_messages(feeds_data, project_id, pubsub_topic_name)

        return f"Batch function triggered for {len(feeds_data)} feeds.", 200
    except Exception as e:
        logging.error("Execution error: %s", e)
        return "Error while fetching feeds.", 500
