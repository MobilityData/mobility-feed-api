import logging
import os

from sqlalchemy.orm import joinedload, contains_eager

from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset, Location
from shared.helpers.database import with_db_session
from shared.helpers.pub_sub import publish_messages

logging.basicConfig(level=logging.INFO)


@with_db_session(echo=False)
def get_feeds_data(db_session):
    countries = os.getenv("COUNTRIES", "Canada")
    countries = [country.strip() for country in countries.split(",")]
    logging.info(f"Getting feeds for countries: {countries}")

    results = (
        db_session.query(Gtfsfeed)
        .join(Gtfsfeed.locations)
        .join(Gtfsfeed.gtfsdatasets)
        .options(joinedload(Gtfsfeed.locations), contains_eager(Gtfsfeed.gtfsdatasets))
        .filter(Location.country.in_(countries))
        .filter(Gtfsfeed.status != "deprecated")
        .filter(Gtfsdataset.latest)
        .populate_existing()
        .all()
    )
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


def reverse_geolocation_batch():
    feeds_data = get_feeds_data()
    logging.info(f"Valid feeds with latest dataset: {len(feeds_data)}")
    pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME", None)
    project_id = os.getenv("PROJECT_ID", None)
    if pubsub_topic_name is None:
        logging.error("PUBSUB_TOPIC_NAME environment variable not set.")
        return "PUBSUB_TOPIC_NAME environment variable not set.", 500
    if project_id is None:
        logging.error("PROJECT_ID environment variable not set.")
        return "PROJECT_ID environment variable not set.", 500

    publish_messages(feeds_data, project_id, pubsub_topic_name)
    logging.info(f"Publishing to topic: {pubsub_topic_name}")
    return f"Batch function triggered for {len(feeds_data)} feeds.", 200
