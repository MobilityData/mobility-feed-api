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
import json
import os
import logging
import time
import random
from dataclasses import dataclass, asdict
from typing import Optional, List
import requests
from requests.exceptions import RequestException, HTTPError
from http import HTTPStatus

import functions_framework
from google.cloud.pubsub_v1.futures import Future
from sqlalchemy.orm import Session
from sqlalchemy import text, select, and_

from helpers.feed_sync.feed_sync_common import FeedSyncProcessor, FeedSyncPayload
from helpers.feed_sync.feed_sync_dispatcher import feed_sync_dispatcher
from helpers.pub_sub import get_pubsub_client, get_execution_id
from dotenv import load_dotenv

# Environment variables
PUBSUB_TOPIC_NAME = os.getenv("PUBSUB_TOPIC_NAME")
PROJECT_ID = os.getenv("PROJECT_ID")
FEEDS_DATABASE_URL = os.getenv("FEEDS_DATABASE_URL")

apikey = os.getenv("TRANSITLAND_API_KEY")

operators_url = os.getenv("Transitland_operator_url")
feeds_url = os.getenv("Transitland_feed_url")
spec = ['gtfs', 'gtfs-rt']

# Create a session instance to reuse connections
session = requests.Session()

@dataclass
class TransitFeedSyncPayload:
    ""
    Data class for transit feed sync payloads.
    ""

    operator_onestop_id: str
    feed_id: str
    feed_url: Optional[str] = None
    execution_id: Optional[str] = None
    external_id: Optional[str] = None
    spec: Optional[str] = None
    auth_info_url: Optional[str] = None
    auth_param_name: Optional[str] = None
    type: Optional[str] = None
    operator_name:Optional[str] = None
    country:Optional[str] = None
    state_province:Optional[str] = None
    city_name:Optional[str] = None
    payload_type: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict())


class TransitFeedSyncProcessor(FeedSyncProcessor):
    def process_sync(self, db_session: Optional[Session] = None, execution_id: Optional[str] = None) -> List[FeedSyncPayload]:
        """
        Process data synchronously to fetch, extract, combine, and prepare payloads for publishing to a queue based on conditions related to the data retrieved from TransitLand API.
        """
        # Fetch data from TransitLand API
        feeds_data = self.get_data(feeds_url, apikey, spec, session)
        operators_data = self.get_data(operators_url, apikey, session=session)

        # Extract feeds and operators data
        feeds = self.extract_feeds_data(feeds_data)
        operators = self.extract_operators_data(operators_data)

        # Combines feeds and operators data
        combined_data = []
        for operator in operators:
            feed = next((f for f in feeds if f['feed_id'] == operator['operator_feed_id']), None)
            if feed and feed['feed_url']:
                combined_data.append({**operator, **feed})

        # Prepares payloads for publishing to queue
        payloads = []
        for data in combined_data:
            # Checks if external_id exists in the public.externalid table
            associated_id = self.get_associated_id(db_session, data['operator_onestop_id'])
            if associated_id:
                # If external_id exists, check if feed_url has changed is feed_url changes then update feed(payload_type="new")
                if not self.check_feed_url_exists(db_session, data['feed_url']):
                    payloads.append(
                        FeedSyncPayload(
                            external_id=data['operator_onestop_id'],
                            payload=TransitFeedSyncPayload(
                                external_id=data['operator_id'],
                                operator_onestop_id=data['operator_onestop_id'],
                                feed_id=data['feed_id'],
                                execution_id=execution_id,
                                feed_url=data['feed_url'],
                                spec=data['spec'],
                                auth_info_url=data['auth_info_url'],
                                auth_param_name=data['auth_param_name'],
                                type=data['type'],
                                operator_name=data['operator_name'],
                                country=data['country'],
                                state_province=data['state_province'],
                                city_name=data['city_name'],
                                payload_type="update"
                            )
                        )
                    )
            else:
                # If external_id does not exist, add the new feed(payload_type="new")
                payloads.append(
                    FeedSyncPayload(
                        external_id=data['operator_onestop_id'],
                        payload=TransitFeedSyncPayload(
                            external_id=data['operator_id'],
                            operator_onestop_id=data['operator_onestop_id'],
                            feed_id=data['feed_id'],
                            execution_id=execution_id,
                            feed_url=data['feed_url'],
                            spec=data['spec'],
                            auth_info_url=data['auth_info_url'],
                            auth_param_name=data['auth_param_name'],
                            type=data['type'],
                            operator_name=data['operator_name'],
                            country=data['country'],
                            state_province=data['state_province'],
                            city_name=data['city_name'],
                            payload_type="new",
                        )
                    )
                )

        return payloads

    def get_data(self, url, apikey, spec=None, session=None, max_retries=3, initial_delay=5, max_delay=60):
        """
           This functions retrieves data from a specified Transitland. Handles rate limits, retries, and error cases.
           Returns the parsed data as a dictionary containing feeds and operators.
           """
        headers = {'apikey': apikey}
        params = {'spec': spec} if spec else {}
        all_data = {'feeds': [], 'operators': []}
        delay = initial_delay

        while url:
            for attempt in range(max_retries):
                try:
                    response = session.get(url, headers=headers, params=params, timeout=30)
                    response.raise_for_status()
                    data = response.json()

                    if 'feeds' in data:
                        all_data['feeds'].extend(data['feeds'])
                    if 'operators' in data:
                        all_data['operators'].extend(data['operators'])

                    meta = data.get('meta', {})
                    url = meta.get('next')
                    delay = initial_delay
                    break

                except (RequestException, HTTPError) as e:
                    if response.status_code not in [404, 500]:
                        print(f"Attempt {attempt + 1} failed: {e}")
                    print(f"Attempt {attempt + 1} failed: {e}")
                    if response.status_code == 429:
                        print(f"Rate limit hit. Waiting for {delay} seconds before retrying.")
                        time.sleep(delay + random.uniform(0, 1))
                        delay = min(delay * 2, max_delay)
                    elif attempt == max_retries - 1:
                        print(f"Failed to fetch data after {max_retries} attempts.")
                        return all_data
                    else:
                        time.sleep(delay)

        return all_data

    def extract_feeds_data(self, feeds_data):
        """
        This function extracts relevant data from a dictionary containing feeds information and returns a list of dictionaries representing each feed.
        Each dictionary in the returned list includes the feed's ID, URL, specification, onestop ID, authorization info URL, authorization parameter name, and authorization type.
        If any of these fields are missing in the input data, corresponding fields in the output dictionary are set to None.
        """
        feeds = []
        for feed in feeds_data['feeds']:
            feed_url = feed['urls'].get('static_current')
            feeds.append({
                'feed_id': feed['id'],
                'feed_url': feed_url,
                'spec': feed['spec'].lower(),
                'feeds_onestop_id': feed['onestop_id'],
                'auth_info_url': feed['authorization'].get('info_url'),
                'auth_param_name': feed['authorization'].get('param_name'),
                'type': feed['authorization'].get('type')
            })
        return feeds

    def extract_operators_data(self, operators_data):
        """
        Extracts relevant data from a given dictionary of operators. Ignores operators associated with places in Japan or France.
        Constructs a list of dictionaries containing information about each operator, including their IDs, names, feed IDs, country, state/province, and city name.
        Returns the list of operators' data.
        """
        operators = []
        for operator in operators_data['operators']:
            if operator.get('agencies') and operator['agencies'][0].get('places'):
                places = operator['agencies'][0]['places']
                if len(places) > 1:
                    place = places[1]
                else:
                    place = places[0]
                if place.get('adm0_name') in ['Japan', 'France']:
                    continue

            operator_data = {
                'operator_id': operator['id'],
                'operator_onestop_id': operator['onestop_id'],
                'operator_name': operator.get('name'),
                'operator_feed_id': operator['feeds'][0]['id'] if operator.get('feeds') else None,
                'country': place.get('adm0_name') if place else None,
                'state_province': place.get('adm1_name') if place else None,
                'city_name': place.get('city_name') if place else None
            }

            operators.append(operator_data)
        return operators

    def get_associated_id(self, db_session: Session, external_id: str) -> Optional[str]:
        """
        Check if the external_id exists in the public.externalid table.
        :param db_session: SQLAlchemy session
        :param external_id: External ID to check
        :return: Associated ID if exists, otherwise None
        """
        query = text("SELECT associated_id FROM public.externalid WHERE associated_id = :external_id")
        result = db_session.execute(query, {'external_id': external_id}).fetchone()
        return result[0] if result else None

    def check_feed_url_exists(self, db_session: Session, feed_url: str) -> bool:
        """
        Check if the feed_url exists in the producer_url column of the public.feed table.
        :param db_session: SQLAlchemy session
        :param feed_url: Feed URL to check
        :return: True if exists, otherwise False
        """
        query = text("SELECT producer_url FROM public.feed WHERE producer_url = :feed_url")
        result = db_session.execute(query, {'feed_url': feed_url}).fetchone()
        return result is not None

    def publish_callback(self, future: Future, payload: FeedSyncPayload, topic_path: str):
        """
        Callback function for when the message is published to Pub/Sub.
        This function logs the result of the publishing operation.
        :param future: Future object
        :param payload: FeedSyncPayload object
        :param topic_path: Pub/Sub topic path
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
    HTTP Function entry point queries the transit land API and publishes events to a Pub/Sub topic to be processed.
    This function requires the following environment variables to be set:
        PUBSUB_TOPIC_NAME: name of the Pub/Sub topic to publish to
        FEEDS_DATABASE_URL: database URL
        PROJECT_ID: GCP project ID
    :param request: HTTP request object
    :return: HTTP response object
    """
    publisher = get_pubsub_client()
    topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC_NAME)
    transit_land_feed_sync_processor = TransitFeedSyncProcessor()
    execution_id = get_execution_id(request, "feed-sync-dispatcher")
    feed_sync_dispatcher(transit_land_feed_sync_processor, topic_path, execution_id)
    return "Feed sync dispatcher executed successfully."