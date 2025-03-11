import logging
import os
from typing import List, Dict, Tuple

import flask
import pycountry
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm.session import Session

from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset, Location
from shared.helpers.database import with_db_session
from shared.helpers.logger import Logger
from shared.helpers.pub_sub import publish_messages

logging.basicConfig(level=logging.INFO)


@with_db_session(echo=False)
def get_feeds_data(country_codes: List[str], db_session: Session) -> List[Dict]:
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
        logging.info(f"Getting feeds for country codes: {country_codes}")
        query = query.filter(
            Gtfsfeed.locations.any(Location.country_code.in_(country_codes))
        )
    else:
        logging.warning("No country codes provided. Fetching feeds for all countries.")

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


def parse_request_parameters(request: flask.Request) -> List[str]:
    """Parse the request parameters to get the country codes."""
    country_codes = request.args.get("country_codes", "").split(",")
    country_codes = [code.strip().upper() for code in country_codes if code]

    # Validate country codes
    for country_code in country_codes:
        if not pycountry.countries.get(alpha_2=country_code):
            raise ValueError(f"Invalid country code: {country_code}")
    return country_codes


def reverse_geolocation_batch(request: flask.Request) -> Tuple[str, int]:
    """Batch function to trigger reverse geolocation for feeds."""
    try:
        Logger.init_logger()
        country_codes = parse_request_parameters(request)
        feeds_data = get_feeds_data(country_codes)
        logging.info(f"Valid feeds with latest dataset: {len(feeds_data)}")

        pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME", None)
        project_id = os.getenv("PROJECT_ID")

        logging.info(f"Publishing to topic: {pubsub_topic_name}")
        publish_messages(feeds_data, project_id, pubsub_topic_name)

        return f"Batch function triggered for {len(feeds_data)} feeds.", 200
    except Exception as e:
        logging.error(f"Execution error: {e}")
        return "Error while fetching feeds.", 500
