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
import base64
import json
import logging
import os
from typing import Optional, List

import functions_framework
from google.cloud import pubsub_v1
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database_gen.sqlacodegen_models import Feed
from helpers.database import start_db_session, configure_polymorphic_mappers
from helpers.feed_sync.models import TransitFeedSyncPayload as FeedPayload
from helpers.logger import Logger
from .feed_processor_utils import check_url_status, create_new_feed

# Environment variables
PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_BATCH_TOPIC = os.getenv("DATASET_BATCH_TOPIC_NAME")
FEEDS_DATABASE_URL = os.getenv("FEEDS_DATABASE_URL")


class FeedProcessor:
    def __init__(self, db_session: Session):
        self.session = db_session
        self.publisher = pubsub_v1.PublisherClient()
        self.feed_stable_id: Optional[str] = None

    def process_feed(self, payload: FeedPayload) -> None:
        """Process a feed based on its database state."""
        try:
            logging.info(
                f"Processing feed: external_id={payload.external_id}, feed_id={payload.feed_id}"
            )
            if not check_url_status(payload.feed_url):
                logging.error(f"Feed URL not reachable: {payload.feed_url}. Skipping.")
                return

            self.feed_stable_id = f"{payload.source}-{payload.stable_id}".lower()
            current_feeds = self._get_current_feeds(payload.external_id, payload.source)

            if not current_feeds:
                new_feed = self._process_new_feed_or_skip(payload)
            else:
                new_feed = self._process_existing_feed_refs(payload, current_feeds)

            self.session.commit()
            self._publish_to_batch_topic_if_needed(payload, new_feed)
        except SQLAlchemyError as e:
            self._rollback_transaction(f"Database error: {str(e)}")
        except Exception as e:
            self._rollback_transaction(f"Error processing feed: {str(e)}")

    def _process_new_feed_or_skip(self, payload: FeedPayload) -> Optional[Feed]:
        """Process a new feed or skip if the URL already exists."""
        if self._check_feed_url_exists(payload.feed_url):
            logging.error(f"Feed URL already exists: {payload.feed_url}. Skipping.")
            return
        logging.info(f"Creating new feed for external_id: {payload.external_id}")
        return create_new_feed(self.session, self.feed_stable_id, payload)

    def _process_existing_feed_refs(
        self, payload: FeedPayload, current_feeds: List[Feed]
    ) -> Optional[Feed]:
        """Process existing feeds, updating if necessary."""
        matching_feeds = [
            f for f in current_feeds if f.producer_url == payload.feed_url
        ]
        if matching_feeds:
            logging.info(f"Feed with URL already exists: {payload.feed_url}. Skipping.")
            return

        stable_id_matches = [
            f for f in current_feeds if self.feed_stable_id in f.stable_id
        ]
        reference_count = len(stable_id_matches)
        active_match = [f for f in stable_id_matches if f.status == "active"]
        if reference_count > 0:
            logging.info(f"Updating feed for stable_id: {self.feed_stable_id}")
            self.feed_stable_id = f"{self.feed_stable_id}_{reference_count}".lower()
            new_feed = self._deprecate_old_feed(payload, active_match[0].id)
        else:
            logging.info(
                f"No matching stable_id. Creating new feed for {payload.external_id}."
            )
            new_feed = create_new_feed(self.session, self.feed_stable_id, payload)
        return new_feed

    def _check_feed_url_exists(self, feed_url: str) -> bool:
        """Check if a feed with the given URL exists."""
        existing_feeds = (
            self.session.query(Feed).filter_by(producer_url=feed_url).count()
        )
        return existing_feeds > 0

    def _get_current_feeds(self, external_id: str, source: str) -> List[Feed]:
        """Retrieve current feeds for a given external ID and source."""
        return (
            self.session.query(Feed)
            .filter(Feed.externalids.any(associated_id=external_id, source=source))
            .all()
        )

    def _deprecate_old_feed(
        self, payload: FeedPayload, old_feed_id: Optional[str]
    ) -> Feed:
        """Update the status of an old feed and create a new one."""
        if old_feed_id:
            old_feed = self.session.get(Feed, old_feed_id)
            if old_feed:
                old_feed.status = "deprecated"
                logging.info(f"Deprecated old feed: {old_feed.id}")
        return create_new_feed(self.session, self.feed_stable_id, payload)

    def _publish_to_batch_topic_if_needed(
        self, payload: FeedPayload, feed: Optional[Feed]
    ) -> None:
        """Publishes a feed to the dataset batch topic if it meets the necessary criteria."""
        if (
            feed is not None
            and feed.authentication_type == "0"  # Authentication type check
            and payload.spec == "gtfs"  # Only for GTFS feeds
        ):
            self._publish_to_topic(feed, payload)

    def _publish_to_topic(self, feed: Feed, payload: FeedPayload) -> None:
        """Publishes the feed to the configured Pub/Sub topic."""
        topic_path = self.publisher.topic_path(PROJECT_ID, DATASET_BATCH_TOPIC)
        logging.debug(f"Publishing to Pub/Sub topic: {topic_path}")

        message_data = {
            "execution_id": payload.execution_id,
            "producer_url": feed.producer_url,
            "feed_stable_id": feed.stable_id,
            "feed_id": feed.id,
            "dataset_id": None,
            "dataset_hash": None,
            "authentication_type": feed.authentication_type,
            "authentication_info_url": feed.authentication_info_url,
            "api_key_parameter_name": feed.api_key_parameter_name,
        }

        try:
            # Convert to JSON string
            json_message = json.dumps(message_data)
            future = self.publisher.publish(
                topic_path, data=json_message.encode("utf-8")
            )
            future.add_done_callback(
                lambda _: logging.info(
                    f"Published feed {feed.stable_id} to dataset batch topic"
                )
            )
            future.result()
            logging.info(f"Message published for feed {feed.stable_id}")
        except Exception as e:
            logging.error(f"Error publishing to dataset batch topic: {str(e)}")
            raise

    def _rollback_transaction(self, message: str) -> None:
        """Rollback the current transaction and log an error."""
        logging.error(message)
        self.session.rollback()


@functions_framework.cloud_event
def process_feed_event(cloud_event) -> None:
    """Cloud Function entry point for feed processing."""
    Logger.init_logger()
    configure_polymorphic_mappers()
    try:
        message_data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        payload = FeedPayload(**json.loads(message_data))
        db_session = start_db_session(FEEDS_DATABASE_URL)
        processor = FeedProcessor(db_session)
        processor.process_feed(payload)
    except Exception as e:
        logging.error(f"Error processing feed event: {str(e)}")
