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
from dataclasses import dataclass, asdict
from typing import Optional

import functions_framework
from google.cloud.pubsub_v1.futures import Future
from sqlalchemy.orm import Session

from helpers.feed_sync.feed_sync_common import FeedSyncProcessor, FeedSyncPayload
from helpers.feed_sync.feed_sync_dispatcher import feed_sync_dispatcher
from helpers.pub_sub import get_pubsub_client, get_execution_id

pubsub_topic_name = os.getenv("PUBSUB_TOPIC_NAME")
project_id = os.getenv("PROJECT_ID")


@dataclass
class TransitFeedSyncPayload:
    """
    Data class for transit feed sync payloads.
    """

    feed_onestop_id: str
    execution_id: Optional[str] = None
    feed_stable_id: Optional[str] = None
    feed_id: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict())


class TransitFeedSyncProcessor(FeedSyncProcessor):
    def process_sync(
        self, session: Session, execution_id: str
    ) -> list[FeedSyncPayload]:
        """
        Process Transit Land Feed Sync.
        :param session: database session
        :param execution_id: execution ID. This ID is used for logging and debugging purposes.
        :return: list of FeedSyncPayload
        """
        # TODO Implement this method
        # Added dummy return to be able to test local debug
        return [
            FeedSyncPayload(
                external_id="dummy",
                payload=TransitFeedSyncPayload(feed_onestop_id="foo_feed_onestop_id"),
            )
        ]

    def publish_callback(
        self, future: Future, payload: FeedSyncPayload, topic_path: str
    ):
        """
        Abstract method for publishing callback.
        :param future: Future object
        :param payload: FeedSyncPayload object
        :param topic_path: Pub/Sub topic path
        """
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
    HTTP Function entry point queries the transit land API and publishes events to a Pub/Sub topic to be processed.
    This function requires the following environment variables to be set:
        PUBSUB_TOPIC_NAME: name of the Pub/Sub topic to publish to
        FEEDS_DATABASE_URL: database URL
        PROJECT_ID: GCP project ID
    :param request: HTTP request object
    :return: HTTP response object
    """
    publisher = get_pubsub_client()
    topic_path = publisher.topic_path(project_id, pubsub_topic_name)
    transit_land_feed_sync_processor = TransitFeedSyncProcessor()
    execution_id = get_execution_id(request, "feed-sync-dispatcher")
    feed_sync_dispatcher(transit_land_feed_sync_processor, topic_path, execution_id)
    return "Feed sync dispatcher executed successfully."
