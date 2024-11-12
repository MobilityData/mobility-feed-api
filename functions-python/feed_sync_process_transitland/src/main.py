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
from sqlalchemy import text
from sqlalchemy.orm import Session

from helpers.database import start_db_session, close_db_session

# Configure logging
logger = logging.getLogger("feed_processor")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s "
                          "- %(levelname)s - %(message)s")
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
    """Handles feed processing operations including database interactions"""

    def __init__(self, db_session: Session):
        self.session = db_session
        self.publisher = pubsub_v1.PublisherClient()

    def process_feed(self, payload: FeedPayload) -> None:
        """
        Processes feed idempotently based on database state, not payload type.
        This function determines the action by checking
        the current state in the database.

        Args:
            payload (FeedPayload): The feed payload to process
        """
        try:
            logger.info(
                f"Starting feed processing "
                f"for external_id: {payload.external_id}"
            )

            # Check current state in database
            current_feed_id, current_url = self.get_current_feed_info(
                payload.external_id, payload.source
            )

            if current_feed_id is None:
                logger.info("Processing new feed")
                # If no existing feed found - checks if URL exists in any feed
                if self.check_feed_url_exists(payload.feed_url):
                    logger.info(f"Feed URL already exists: {payload.feed_url}")
                    return
                # Create new feed
                self.process_new_feed(payload)
            else:
                # If Feed exists - check if URL has changed
                if current_url != payload.feed_url:
                    logger.info("Processing feed update")
                    logger.debug(
                        f"Found existing feed: "
                        f"{current_feed_id} with different URL"
                    )
                    # URL changed - handle update
                    self.process_feed_update(payload, current_feed_id)
                else:
                    logger.info(
                        f"Feed already exists with "
                        f"same URL: {payload.external_id}"
                    )
                    return

            self.session.commit()
            logger.debug("Database transaction committed successfully")

            # Publish to dataset batch topic if not authenticated
            if not payload.auth_info_url:
                self.publish_to_batch_topic(payload)

        except Exception as e:
            error_msg = (f"Error processing "
                         f"feed {payload.external_id}: {str(e)}")
            logger.error(error_msg)
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
            f"Starting new feed creation "
            f"for external_id: {payload.external_id}"
        )

        # Checks if feed with same URL exists
        if self.check_feed_url_exists(payload.feed_url):
            logger.info(f"Feed URL already exists: {payload.feed_url}")
            return

        # Generate new feed ID and stable ID
        feed_id = str(uuid.uuid4())
        stable_id = f"{payload.source}-{payload.external_id}"

        logger.debug(f"Generated new feed_id: "
                     f"{feed_id} and stable_id: {stable_id}")

        try:
            # Insert new feed
            feed_query = text(
                """
                INSERT INTO public.feed (
                    id,
                    data_type,
                    feed_name,
                    producer_url,
                    authentication_type,
                    authentication_info_url,
                    api_key_parameter_name,
                    stable_id,
                    status,
                    feed_contact_email,
                    provider,
                    created_at
                ) VALUES (
                    :feed_id,
                    :data_type,
                    :feed_name,
                    :producer_url,
                    CASE
                        WHEN :auth_type IS NOT NULL THEN
                        cast(:auth_type as authenticationtype)
                        ELSE '0'::authenticationtype
                    END,
                    :auth_info_url,
                    :api_key_parameter_name,
                    :stable_id,
                    'active'::status,
                    NULL,
                    :provider,
                    CURRENT_TIMESTAMP
                )
            """
            )

            self.session.execute(
                feed_query,
                {
                    "feed_id": feed_id,
                    "data_type": payload.spec,
                    "feed_name": f"Feed from {payload.operator_name}"
                    if payload.operator_name
                    else "Unnamed Feed",
                    "producer_url": payload.feed_url,
                    "auth_type": payload.type,
                    "auth_info_url": payload.auth_info_url,
                    "api_key_parameter_name": payload.auth_param_name,
                    "stable_id": stable_id,
                    "provider": payload.operator_name,
                },
            )

            logger.debug(
                f"Successfully inserted new feed record for feed_id: {feed_id}"
            )

            # Create external ID mapping
            external_id_query = text(
                """
                INSERT INTO public.externalid (feed_id, associated_id, source)
                VALUES (:feed_id, :external_id, :source)
            """
            )

            self.session.execute(
                external_id_query,
                {
                    "feed_id": feed_id,
                    "external_id": payload.external_id,
                    "source": payload.source,
                },
            )

            logger.debug(
                f"Successfully created external ID "
                f"mapping for feed_id: {feed_id}"
            )
            logger.info(
                f"Created new feed with ID: {feed_id} for "
                f"external_id: {payload.external_id}"
            )

        except Exception as e:
            logger.error(
                f"Error creating new feed for "
                f"external_id {payload.external_id}: {str(e)}"
            )
            raise

    def process_feed_update(self, payload: FeedPayload, old_feed_id: str) \
            -> None:
        """
        Process feed update when URL has changed

        Args:
            payload (FeedPayload): The feed payload for update
            old_feed_id (str): The ID of the existing feed to be updated
        """
        logger.info(
            f"Starting feed update process for "
            f"external_id: {payload.external_id}"
        )
        logger.debug(f"Old feed_id: {old_feed_id}, "
                     f"New URL: {payload.feed_url}")

        try:
            # Create new feed with updated URL
            new_feed_id = str(uuid.uuid4())
            stable_id = f"{payload.source}-{payload.external_id}"

            logger.debug(f"Generated new feed_id: {new_feed_id} for update")

            # Insert new feed
            new_feed_query = text(
                """
                INSERT INTO public.feed (
                    id, data_type,
                    feed_name,
                    producer_url,
                    authentication_type,
                    authentication_info_url,
                    api_key_parameter_name,
                    stable_id,
                    status,
                    feed_contact_email,
                    provider,
                    created_at
                ) VALUES (
                    feed_id,
                :data_type,
                :feed_name,
                :producer_url,
                CASE
                    WHEN :auth_type IS NOT NULL THEN
                    cast(:auth_type as authenticationtype)
                    ELSE '0'::authenticationtype
                END,
                :auth_info_url,
                :api_key_parameter_name,
                :stable_id,
                'active'::status,
                NULL,
                :provider,
                CURRENT_TIMESTAMP
                )
            """
            )

            self.session.execute(
                new_feed_query,
                {
                    "feed_id": new_feed_id,
                    "data_type": payload.spec,
                    "feed_name": f"Feed from {payload.operator_name}"
                    if payload.operator_name
                    else "Unnamed Feed",
                    "producer_url": payload.feed_url,
                    "auth_type": payload.type,
                    "auth_info_url": payload.auth_info_url,
                    "api_key_parameter_name": payload.auth_param_name,
                    "stable_id": stable_id,
                    "provider": payload.operator_name,
                },
            )

            logger.debug(
                f"Successfully inserted new feed "
                f"record for feed_id: {new_feed_id}"
            )

            # Update old feed status to deprecated
            logger.debug(f"Deprecating old feed ID: {old_feed_id}")
            deprecate_query = text(
                """
                UPDATE public.feed
                SET status = 'deprecated'::status
                WHERE id = :old_feed_id
            """
            )
            self.session.execute(deprecate_query, {"old_feed_id": old_feed_id})

            # Update external ID mapping
            logger.debug(f"Updating external ID mapping "
                         f"to new feed_id: {new_feed_id}")
            update_external_id_query = text(
                """
                UPDATE public.externalid
                SET feed_id = :new_feed_id
                WHERE associated_id = :external_id AND source = :source
            """
            )
            self.session.execute(
                update_external_id_query,
                {
                    "new_feed_id": new_feed_id,
                    "external_id": payload.external_id,
                    "source": payload.source,
                },
            )

            # Add entry to redirecting ID table
            logger.debug(f"Creating redirect from "
                         f"{old_feed_id} to {new_feed_id}")
            redirect_query = text(
                """
                INSERT INTO public.redirectingid (source_id, target_id)
                VALUES (:old_feed_id, :new_feed_id)
            """
            )
            self.session.execute(
                redirect_query, {"old_feed_id": old_feed_id,
                                 "new_feed_id": new_feed_id}
            )

            logger.info(
                f"Updated feed for external_id: {payload.external_id}, "
                f"new feed_id: {new_feed_id}"
            )

        except Exception as e:
            logger.error(
                f"Error updating feed for "
                f"external_id {payload.external_id}: {str(e)}"
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
        query = text(
            """
            SELECT 1 FROM public.feed
            WHERE producer_url = :feed_url AND status = 'active'::status
            LIMIT 1
        """
        )
        result = self.session.execute(query, {"feed_url": feed_url}).fetchone()

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
        query = text(
            """
            SELECT f.id, f.producer_url
            FROM public.feed f
            JOIN public.externalid e ON f.id = e.feed_id
            WHERE e.associated_id = :external_id
            AND e.source = :source
            AND f.status = 'active'::status
            LIMIT 1
        """
        )
        result = self.session.execute(
            query, {"external_id": external_id, "source": source}
        ).fetchone()
        if result:
            logger.debug(f"Retrieved current feed "
                         f"info for external_id: {external_id}")
            return result[0], result[1]

        logger.debug(f"No existing feed found for external_id: {external_id}")
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
            logger.info(f"Published feed {payload.feed_id} "
                        f"to dataset batch topic")
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
        pubsub_message = (
            base64.b64decode(cloud_event.data["message"]["data"]).decode())
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
