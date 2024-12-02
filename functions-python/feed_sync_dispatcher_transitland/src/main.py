#
#   MobilityData 2024
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

import logging
import os
import random
import time
from typing import Optional

import functions_framework
import pandas as pd
import requests
from google.cloud.pubsub_v1.futures import Future
from requests.exceptions import RequestException, HTTPError
from sqlalchemy.orm import Session

from database_gen.sqlacodegen_models import Feed
from helpers.feed_sync.feed_sync_common import FeedSyncProcessor, FeedSyncPayload
from helpers.feed_sync.feed_sync_dispatcher import feed_sync_dispatcher
from helpers.feed_sync.models import TransitFeedSyncPayload
from helpers.logger import Logger
from helpers.pub_sub import get_pubsub_client, get_execution_id
from typing import Tuple, List
from collections import defaultdict


# Environment variables
PUBSUB_TOPIC_NAME = os.getenv("PUBSUB_TOPIC_NAME")
PROJECT_ID = os.getenv("PROJECT_ID")
FEEDS_DATABASE_URL = os.getenv("FEEDS_DATABASE_URL")
TRANSITLAND_API_KEY = os.getenv("TRANSITLAND_API_KEY")
TRANSITLAND_OPERATOR_URL = os.getenv("TRANSITLAND_OPERATOR_URL")
TRANSITLAND_FEED_URL = os.getenv("TRANSITLAND_FEED_URL")

# session instance to reuse connections
session = requests.Session()


def process_feed_urls(feed: dict, urls_in_db: List[str]) -> Tuple[List[str], List[str]]:
    """
    Extracts the valid feed URLs and their corresponding entity types from the feed dictionary. If the same URL
    corresponds to multiple entity types, the types are concatenated with a comma.
    """
    url_keys_to_types = {
        "static_current": "",
        "realtime_alerts": "sa",
        "realtime_trip_updates": "tu",
        "realtime_vehicle_positions": "vp",
    }

    urls = feed.get("urls", {})
    url_to_entity_types = defaultdict(list)

    for key, entity_type in url_keys_to_types.items():
        if (url := urls.get(key)) and (url not in urls_in_db):
            if entity_type:
                logging.info(f"Found URL for entity type: {entity_type}")
            url_to_entity_types[url].append(entity_type)

    valid_urls = []
    entity_types = []

    for url, types in url_to_entity_types.items():
        valid_urls.append(url)
        logging.info(f"URL = {url}, Entity types = {types}")
        entity_types.append(",".join(types))

    return valid_urls, entity_types


class TransitFeedSyncProcessor(FeedSyncProcessor):
    def process_sync(
        self, db_session: Session, execution_id: Optional[str] = None
    ) -> List[FeedSyncPayload]:
        """
        Process data synchronously to fetch, extract, combine, filter and prepare payloads for publishing
        to a queue based on conditions related to the data retrieved from TransitLand API.
        """
        feeds_data_gtfs_rt = self.get_data(
            TRANSITLAND_FEED_URL, TRANSITLAND_API_KEY, "gtfs_rt", session
        )
        logging.info(
            "Fetched %s GTFS-RT feeds from TransitLand API",
            len(feeds_data_gtfs_rt["feeds"]),
        )

        feeds_data_gtfs = self.get_data(
            TRANSITLAND_FEED_URL, TRANSITLAND_API_KEY, "gtfs", session
        )
        logging.info(
            "Fetched %s GTFS feeds from TransitLand API", len(feeds_data_gtfs["feeds"])
        )
        feeds_data = feeds_data_gtfs["feeds"] + feeds_data_gtfs_rt["feeds"]

        operators_data = self.get_data(
            TRANSITLAND_OPERATOR_URL, TRANSITLAND_API_KEY, session=session
        )
        logging.info(
            "Fetched %s operators from TransitLand API",
            len(operators_data["operators"]),
        )
        all_urls = list(db_session.query(Feed.producer_url).all())
        feeds = self.extract_feeds_data(feeds_data, all_urls)
        operators = self.extract_operators_data(operators_data)

        # Converts operators and feeds to pandas DataFrames
        operators_df = pd.DataFrame(operators)
        feeds_df = pd.DataFrame(feeds)

        # Merge operators and feeds DataFrames on 'operator_feed_id' and 'feed_id'
        combined_df = pd.merge(
            operators_df,
            feeds_df,
            left_on="operator_feed_id",
            right_on="feed_id",
            how="inner",
        )

        # Filtered out rows where 'feed_url' is missing
        combined_df = combined_df[combined_df["feed_url"].notna()]

        # Group by 'stable_id' and concatenate 'operator_name' while keeping first values of other columns
        df_grouped = (
            combined_df.groupby("stable_id")
            .agg(
                {
                    "operator_name": lambda x: ", ".join(x),
                    "feeds_onestop_id": "first",
                    "feed_id": "first",
                    "feed_url": "first",
                    "operator_feed_id": "first",
                    "spec": "first",
                    "entity_types": "first",
                    "country": "first",
                    "state_province": "first",
                    "city_name": "first",
                    "auth_info_url": "first",
                    "auth_param_name": "first",
                    "type": "first",
                }
            )
            .reset_index()
        )

        # Filtered out unwanted countries
        countries_not_included = ["France", "Japan"]
        filtered_df = df_grouped[
            ~df_grouped["country"]
            .str.lower()
            .isin([c.lower() for c in countries_not_included])
        ]
        logging.info(
            "Filtered out %s feeds from countries: %s",
            len(df_grouped) - len(filtered_df),
            countries_not_included,
        )

        # Filtered out URLs that return undesired status codes
        filtered_df = filtered_df.drop_duplicates(
            subset=["feed_url"]
        )  # Drop duplicates

        # Convert filtered DataFrame to dictionary format
        combined_data = filtered_df.to_dict(orient="records")
        logging.info("Prepared %s feeds for publishing", len(combined_data))

        payloads = []
        for data in combined_data:
            external_id = data["feeds_onestop_id"]
            feed_url = data["feed_url"]
            source = "TLD"

            if not self.check_external_id(db_session, external_id, source):
                payload_type = "new"
            else:
                mbd_feed_url = self.get_mbd_feed_url(db_session, external_id, source)
                if mbd_feed_url != feed_url:
                    payload_type = "update"
                else:
                    continue

            # prepare payload
            payload = TransitFeedSyncPayload(
                external_id=external_id,
                stable_id=data["stable_id"],
                entity_types=data["entity_types"],
                feed_id=data["feed_id"],
                execution_id=execution_id,
                feed_url=feed_url,
                spec=data["spec"],
                auth_info_url=data["auth_info_url"],
                auth_param_name=data["auth_param_name"],
                type=data["type"],
                operator_name=data["operator_name"],
                country=data["country"],
                state_province=data["state_province"],
                city_name=data["city_name"],
                source="TLD",
                payload_type=payload_type,
            )
            payloads.append(FeedSyncPayload(external_id=external_id, payload=payload))

        return payloads

    def get_data(
        self,
        url,
        api_key,
        spec=None,
        session=None,
        max_retries=3,
        initial_delay=60,
        max_delay=120,
    ):
        """
        This function retrieves data from the specified Transitland feeds and operator endpoints.
        Handles rate limits, retries, and error cases.
        Returns the parsed data as a dictionary containing feeds and operators.
        """
        headers = {"apikey": api_key}
        params = {"spec": spec} if spec else {}
        all_data = {"feeds": [], "operators": []}
        delay = initial_delay
        response = None

        logging.info("Fetching data from %s", url)
        while url:
            for attempt in range(max_retries):
                try:
                    response = session.get(
                        url, headers=headers, params=params, timeout=30
                    )
                    response.raise_for_status()
                    data = response.json()
                    all_data["feeds"].extend(data.get("feeds", []))
                    all_data["operators"].extend(data.get("operators", []))
                    url = data.get("meta", {}).get("next")
                    logging.info(
                        "Fetched %s feeds and %s operators",
                        len(all_data["feeds"]),
                        len(all_data["operators"]),
                    )
                    logging.info("Next URL: %s", url)
                    delay = initial_delay
                    break
                except (RequestException, HTTPError) as e:
                    logging.error("Attempt %s failed: %s", attempt + 1, e)
                    if response is not None and response.status_code == 429:
                        logging.warning("Rate limit hit. Waiting for %s seconds", delay)
                        time.sleep(delay + random.uniform(0, 1))
                        delay = min(delay * 2, max_delay)
                    elif attempt == max_retries - 1:
                        logging.error(
                            "Failed to fetch data after %s attempts.", max_retries
                        )
                        return all_data
                    else:
                        logging.info("Retrying in %s seconds", delay)
                        time.sleep(delay)
        logging.info("Finished fetching data.")
        return all_data

    def extract_feeds_data(self, feeds_data: dict, urls_in_db: List[str]) -> List[dict]:
        """
        This function extracts relevant data from the Transitland feeds endpoint containing feeds information.
        Returns a list of dictionaries representing each feed.
        """
        feeds = []
        for feed in feeds_data:
            feed_urls, entity_types = process_feed_urls(feed, urls_in_db)
            logging.info("Feed %s has %s valid URL(s)", feed["id"], len(feed_urls))
            logging.info("Feed %s entity types: %s", feed["id"], entity_types)
            if len(feed_urls) == 0:
                logging.warning("Feed URL not found for feed %s", feed["id"])
                continue

            for feed_url, entity_types in zip(feed_urls, entity_types):
                if entity_types is not None and len(entity_types) > 0:
                    stable_id = f"{feed['id']}-{entity_types.replace(',', '_')}"
                else:
                    stable_id = feed["id"]
                logging.info("Stable ID: %s", stable_id)
                feeds.append(
                    {
                        "feed_id": feed["id"],
                        "stable_id": stable_id,
                        "feed_url": feed_url,
                        "entity_types": entity_types if len(entity_types) > 0 else None,
                        "spec": feed["spec"].lower(),
                        "feeds_onestop_id": feed["onestop_id"],
                        "auth_info_url": feed["authorization"].get("info_url"),
                        "auth_param_name": feed["authorization"].get("param_name"),
                        "type": feed["authorization"].get("type"),
                    }
                )
        return feeds

    def extract_operators_data(self, operators_data: dict) -> List[dict]:
        """
        This function extracts relevant data from the Transitland operators endpoint.
        Constructs a list of dictionaries containing information about each operator.
        """
        operators = []
        for operator in operators_data["operators"]:
            if operator.get("agencies") and operator["agencies"][0].get("places"):
                places = operator["agencies"][0]["places"]
                place = places[1] if len(places) > 1 else places[0]

                for related_feed in operator.get("feeds", []):
                    operator_data = {
                        "operator_name": operator.get("name"),
                        "operator_feed_id": related_feed["id"],
                        "country": place.get("adm0_name") if place else None,
                        "state_province": place.get("adm1_name") if place else None,
                        "city_name": place.get("city_name") if place else None,
                    }
                    operators.append(operator_data)
        return operators

    def check_external_id(
        self, db_session: Session, external_id: str, source: str
    ) -> bool:
        """
        Checks if the external_id exists in the public.externalid table for the given source.
        :param db_session: SQLAlchemy session
        :param external_id: The external_id (feeds_onestop_id) to check
        :param source: The source to filter by (e.g., 'TLD' for TransitLand)
        :return: True if the feed exists, False otherwise
        """
        results = (
            db_session.query(Feed)
            .filter(Feed.externalids.any(associated_id=external_id))
            .all()
        )
        return results is not None and len(results) > 0

    def get_mbd_feed_url(
        self, db_session: Session, external_id: str, source: str
    ) -> Optional[str]:
        """
        Retrieves the feed_url from the public.feed table in the mbd for the given external_id.
        :param db_session: SQLAlchemy session
        :param external_id: The external_id (feeds_onestop_id) from TransitLand
        :param source: The source to filter by (e.g., 'TLD' for TransitLand)
        :return: feed_url in mbd if exists, otherwise None
        """
        results = (
            db_session.query(Feed)
            .filter(Feed.externalids.any(associated_id=external_id))
            .all()
        )
        return results[0].producer_url if results else None

    def publish_callback(
        self, future: Future, payload: FeedSyncPayload, topic_path: str
    ):
        """
        Callback function for when the message is published to Pub/Sub.
        This function logs the result of the publishing operation.
        """
        if future.exception():
            print(
                f"Error publishing transit land feed {payload.external_id} "
                f"to Pub/Sub topic {topic_path}: {future.exception()}"
            )
        else:
            print(f"Published transit land feed {payload.external_id}.")


@functions_framework.http
def feed_sync_dispatcher_transitland(request):
    """
    HTTP Function entry point queries the transitland API and publishes events to a Pub/Sub topic to be processed.
    """
    Logger.init_logger()
    publisher = get_pubsub_client()
    topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC_NAME)
    transit_land_feed_sync_processor = TransitFeedSyncProcessor()
    execution_id = get_execution_id(request, "feed-sync-dispatcher")
    feed_sync_dispatcher(transit_land_feed_sync_processor, topic_path, execution_id)
    return "Feed sync dispatcher executed successfully."
