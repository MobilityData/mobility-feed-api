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
import uuid
from dataclasses import dataclass
from typing import Optional, Tuple

import functions_framework
from google.cloud import pubsub_v1
from sqlalchemy.orm import Session
from database_gen.sqlacodegen_models import Feed, Externalid, Redirectingid

from helpers.database import start_db_session, close_db_session

# Configure logging
logger = logging.getLogger("feed_processor")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s " "- %(levelname)s - %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Environment variables
PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_BATCH_TOPIC = os.getenv("DATASET_BATCH_TOPIC_NAME")
FEEDS_DATABASE_URL = os.getenv("FEEDS_DATABASE_URL")


@dataclass
class FeedPayload:
    """Data class for feed processing payload"""

    external_id: str
    feed_id: str
    feed_url: str
    execution_id: Optional[str]
    spec: str
    auth_info_url: Optional[str]
    auth_param_name: Optional[str]
    type: Optional[str]
    operator_name: Optional[str]
    country: Optional[str]
    state_province: Optional[str]
    city_name: Optional[str]
    source: str
    payload_type: str


class FeedProcessor:
    """Handles feed processing operations"""

    def __init__(self, db_session: Session):
        self.session = db_session
        self.publisher = pubsub_v1.PublisherClient()

    def process_feed(self, payload: FeedPayload) -> None:
        """
        Processes feed idempotently based on database state

        Args:
            payload (FeedPayload): The feed payload to process
        """
        try:
            logger.info(
                f"Starting feed processing for external_id: {payload.external_id}"
            )

            # Check current state of feed in database
            current_feed_id, current_url = self.get_current_feed_info(
                payload.external_id, payload.source
            )

            if current_feed_id is None:
                logger.info("Processing new feed")
                # If no existing feed_id found - check if URL exists in any feed
                if self.check_feed_url_exists(payload.feed_url):
                    logger.info(f"Feed URL already exists: {payload.feed_url}")
                    return
                self.process_new_feed(payload)
            else:
                # If Feed exists - check if URL has changed
                if current_url != payload.feed_url:
                    logger.info("Processing feed update")
                    logger.debug(
                        f"Found existing feed: {current_feed_id} with different URL"
                    )
                    self.process_feed_update(payload, current_feed_id)
                else:
                    logger.info(
                        f"Feed already exists with same URL: {payload.external_id}"
                    )
                    return

            self.session.commit()
            logger.debug("Database transaction committed successfully")

            # Publish to dataset_batch_topic if not authenticated
            if not payload.auth_info_url:
                self.publish_to_batch_topic(payload)

        except Exception as e:
            error_msg = f"Error processing feed {payload.external_id}: {str(e)}"
            logger.error(error_msg)
            if "payload" in locals():
                self.session.rollback()
                logger.debug("Database transaction rolled back due to error")
            raise

    def process_new_feed(self, payload: FeedPayload) -> None:
        """
        Process creation of a new feed

        Args:
            payload (FeedPayload): The feed payload for new feed
        """

        logger.info(
            f"Starting new feed creation for external_id: {payload.external_id}"
        )

        # Check if feed with same URL exists
        if self.check_feed_url_exists(payload.feed_url):
            logger.info(f"Feed URL already exists: {payload.feed_url}")
            return

        # Generate new feed ID and stable ID
        feed_id = str(uuid.uuid4())
        stable_id = f"{payload.source}-{payload.external_id}"

        logger.debug(f"Generated new feed_id: {feed_id} and stable_id: {stable_id}")

        try:
            # Create new feed
            new_feed = Feed(
                id=feed_id,
                data_type=payload.spec,
                feed_name=f"Feed from {payload.operator_name}"
                if payload.operator_name
                else "Unnamed Feed",
                producer_url=payload.feed_url,
                authentication_type=payload.type if payload.type else "0",
                authentication_info_url=payload.auth_info_url,
                api_key_parameter_name=payload.auth_param_name,
                stable_id=stable_id,
                status="active",
                provider=payload.operator_name,
            )

            # external ID mapping
            external_id = Externalid(
                feed_id=feed_id,
                associated_id=payload.external_id,
                source=payload.source,
            )

            # Add relationships
            new_feed.externalids.append(external_id)

            self.session.add(new_feed)
            self.session.flush()

            logger.debug(f"Successfully created feed with ID: {feed_id}")
            logger.info(
                f"Created new feed with ID: {feed_id} for external_id: {payload.external_id}"
            )

        except Exception as e:
            logger.error(
                f"Error creating new feed for external_id {payload.external_id}: {str(e)}"
            )
            raise

    def process_feed_update(self, payload: FeedPayload, old_feed_id: str) -> None:
        """
        Process feed update when URL has changed

        Args:
            payload (FeedPayload): The feed payload for update
            old_feed_id (str): The ID of the existing feed to be updated
        """

        logger.info(
            f"Starting feed update process for external_id: {payload.external_id}"
        )
        logger.debug(f"Old feed_id: {old_feed_id}, New URL: {payload.feed_url}")

        try:
            # Create new feed with updated URL
            new_feed_id = str(uuid.uuid4())
            stable_id = f"{payload.source}-{payload.external_id}"

            # Create new feed
            new_feed = Feed(
                id=new_feed_id,
                data_type=payload.spec,
                feed_name=f"Feed from {payload.operator_name}"
                if payload.operator_name
                else "Unnamed Feed",
                producer_url=payload.feed_url,
                authentication_type=payload.type if payload.type else "0",
                authentication_info_url=payload.auth_info_url,
                api_key_parameter_name=payload.auth_param_name,
                stable_id=stable_id,
                status="active",
                provider=payload.operator_name,
            )

            # Add new feed to session
            self.session.add(new_feed)

            # Update old feed status to deprecated
            old_feed = self.session.get(Feed, old_feed_id)
            if old_feed:
                old_feed.status = "deprecated"
                logger.debug(f"Deprecating old feed ID: {old_feed_id}")

            # Update external ID mapping
            existing_external_id = (
                self.session.query(Externalid)
                .filter(
                    Externalid.associated_id == payload.external_id,
                    Externalid.source == payload.source,
                )
                .first()
            )

            if existing_external_id:
                existing_external_id.feed_id = new_feed_id
                logger.debug(
                    f"Updated external ID mapping to new feed_id: {new_feed_id}"
                )

            # Create redirect
            redirect = Redirectingid(source_id=old_feed_id, target_id=new_feed_id)
            self.session.add(redirect)
            logger.debug(f"Created redirect from {old_feed_id} to {new_feed_id}")

            # Flush changes to get IDs
            self.session.flush()

            logger.info(
                f"Updated feed for external_id: {payload.external_id}, new feed_id: {new_feed_id}"
            )

        except Exception as e:
            logger.error(
                f"Error updating feed for external_id {payload.external_id}: {str(e)}"
            )
            raise

    def check_feed_url_exists(self, feed_url: str) -> bool:
        """
        Check if a feed with the given URL already exists

        Args:
            feed_url (str): The URL to check

        Returns:
            bool: True if URL exists, False otherwise
        """
        result = (
            self.session.query(Feed)
            .filter(Feed.producer_url == feed_url, Feed.status == "active")
            .first()
        )

        if result is not None:
            logger.debug(f"Found existing feed with URL: {feed_url}")
            return True

        logger.debug(f"No existing feed found with URL: {feed_url}")
        return False

    def get_current_feed_info(
        self, external_id: str, source: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get current feed ID and URL for given external ID

        Args:
            external_id (str): The external ID to look up
            source (str): The source of the feed

        Returns:
            Tuple[Optional[str], Optional[str]]: Tuple of (feed_id, feed_url)
        """
        result = (self.session
                  .query(Feed)
                  .filter(
            Feed.externalids.any(
                associated_id=external_id,
                source=source
            ),
            Feed.status == "active")
                  .first()
         )
        if result is not None:
            logger.info(
                f"Retrieved feed {result.stable_id} info for external_id: {external_id}"
            )
            return result.id, result.producer_url
        logging.info(f"No existing feed found for external_id: {external_id}")
        return None, None

    def publish_to_batch_topic(self, payload: FeedPayload) -> None:
        """
        Publish feed to dataset batch topic

        Args:
            payload (FeedPayload): The feed payload to publish
        """
        topic_path = self.publisher.topic_path(PROJECT_ID, DATASET_BATCH_TOPIC)
        logger.debug(f"Publishing to topic: {topic_path}")

        data = json.dumps(
            {"feed_id": payload.feed_id, "execution_id": payload.execution_id}
        ).encode("utf-8")

        try:
            logger.debug(f"Preparing to publish feed_id: {payload.feed_id}")
            future = self.publisher.publish(topic_path, data=data)
            future.result()
            logger.info(f"Published feed {payload.feed_id} " f"to dataset batch topic")
        except Exception as e:
            error_msg = f"Error publishing to dataset batch topic: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)


@functions_framework.cloud_event
def process_feed_event(cloud_event):
    """
    Cloud Function to process feed events from Pub/Sub

    Args:
        cloud_event (CloudEvent): The cloud event
        containing the Pub/Sub message
    """
    try:
        # Decode payload from Pub/Sub message
        pubsub_message = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        message_data = json.loads(pubsub_message)

        payload = FeedPayload(**message_data)

        db_session = start_db_session(FEEDS_DATABASE_URL)

        try:
            processor = FeedProcessor(db_session)
            processor.process_feed(payload)

            logger.info(f"Successfully processed feed: {payload.external_id}")
            return "Success", 200

        finally:
            close_db_session(db_session)

    except Exception as e:
        error_msg = f"Error processing feed event: {str(e)}"
        logger.error(error_msg)
        return error_msg, 500
