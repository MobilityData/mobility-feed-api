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
from typing import Optional, Tuple

import functions_framework
from google.cloud import pubsub_v1
from sqlalchemy.orm import Session
from database_gen.sqlacodegen_models import Feed, Externalid, Redirectingid
from sqlalchemy.exc import SQLAlchemyError

from helpers.database import start_db_session, close_db_session
from helpers.logger import Logger, StableIdFilter
from helpers.feed_sync.models import TransitFeedSyncPayload as FeedPayload
from helpers.locations import create_or_get_location

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("feed_processor")
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Initialize GCP logger for cloud environment
Logger.init_logger()
gcp_logger = Logger("feed_processor").get_logger()


def log_message(level, message):
    """Log messages to both local and GCP loggers"""
    if level == "info":
        logger.info(message)
        gcp_logger.info(message)
    elif level == "error":
        logger.error(message)
        gcp_logger.error(message)
    elif level == "warning":
        logger.warning(message)
        gcp_logger.warning(message)
    elif level == "debug":
        logger.debug(message)
        gcp_logger.debug(message)


# Environment variables
PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_BATCH_TOPIC = os.getenv("DATASET_BATCH_TOPIC_NAME")
FEEDS_DATABASE_URL = os.getenv("FEEDS_DATABASE_URL")


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
        gcp_logger.addFilter(StableIdFilter(payload.external_id))
        try:
            log_message(
                "info",
                f"Starting feed processing for external_id: {payload.external_id}",
            )

            # Check current state of feed in database
            current_feed_id, current_url = self.get_current_feed_info(
                payload.external_id, payload.source
            )

            if current_feed_id is None:
                log_message("info", "Processing new feed")
                # If no existing feed_id found - check if URL exists in any feed
                if self.check_feed_url_exists(payload.feed_url):
                    log_message("error", f"Feed URL already exists: {payload.feed_url}")
                    return
                self.process_new_feed(payload)
            else:
                # If Feed exists - check if URL has changed
                if current_url != payload.feed_url:
                    log_message("info", "Processing feed update")
                    log_message(
                        "debug",
                        f"Found existing feed: {current_feed_id} with different URL",
                    )
                    self.process_feed_update(payload, current_feed_id)
                else:
                    log_message(
                        "error",
                        f"Feed already exists with same URL: {payload.external_id}",
                    )
                    return

            self.session.commit()
            log_message("debug", "Database transaction committed successfully")

            # Publish to dataset_batch_topic if not authenticated
            if not payload.auth_info_url:
                self.publish_to_batch_topic(payload)

        except SQLAlchemyError as e:
            error_msg = (
                f"Database error processing feed {payload.external_id}: {str(e)}"
            )
            log_message("error", error_msg)
            self.session.rollback()
            log_message("error", "Database transaction rolled back due to error")
            raise
        except Exception as e:
            error_msg = f"Error processing feed {payload.external_id}: {str(e)}"
            log_message("error", error_msg)
            self.session.rollback()
            log_message("error", "Database transaction rolled back due to error")
            raise

    def process_new_feed(self, payload: FeedPayload) -> None:
        """
        Process creation of a new feed

        Args:
            payload (FeedPayload): The feed payload for new feed
        """
        log_message(
            "info", f"Starting new feed creation for external_id: {payload.external_id}"
        )

        # Check if feed with same URL exists
        if self.check_feed_url_exists(payload.feed_url):
            log_message("error", f"Feed URL already exists: {payload.feed_url}")
            return

        # Generate new feed ID and stable ID
        feed_id = str(uuid.uuid4())
        stable_id = f"{payload.source}-{payload.external_id}"

        log_message(
            "debug", f"Generated new feed_id: {feed_id} and stable_id: {stable_id}"
        )

        try:
            # Create new feed
            new_feed = Feed(
                id=feed_id,
                data_type=payload.spec,
                producer_url=payload.feed_url,
                authentication_type=payload.type if payload.type else "0",
                authentication_info_url=payload.auth_info_url,
                api_key_parameter_name=payload.auth_param_name,
                stable_id=stable_id,
                status="active",
                provider=payload.operator_name,
                operational_status="wip",
            )

            # external ID mapping
            external_id = Externalid(
                feed_id=feed_id,
                associated_id=payload.external_id,
                source=payload.source,
            )

            # Add relationships
            new_feed.externalids.append(external_id)

            # Create or get location
            location = create_or_get_location(
                self.session, payload.country, payload.state_province, payload.city_name
            )

            if location is not None:  # Only append if location is not None
                new_feed.locations.append(location)
                log_message("debug", f"Added location information for feed: {feed_id}")
            else:
                log_message(
                    "debug", f"No location information to add for feed: {feed_id}"
                )

            self.session.add(new_feed)
            self.session.flush()

            log_message("debug", f"Successfully created feed with ID: {feed_id}")
            log_message(
                "info",
                f"Created new feed with ID: {feed_id} for external_id: {payload.external_id}",
            )

        except Exception as e:
            log_message(
                "error",
                f"Error creating new feed for external_id {payload.external_id}: {str(e)}",
            )
            raise

    def process_feed_update(self, payload: FeedPayload, old_feed_id: str) -> None:
        """
        Process feed update when URL has changed

        Args:
            payload (FeedPayload): The feed payload for update
            old_feed_id (str): The ID of the existing feed to be updated
        """
        log_message(
            "info",
            f"Starting feed update process for external_id: {payload.external_id}",
        )
        log_message("debug", f"Old feed_id: {old_feed_id}, New URL: {payload.feed_url}")

        try:
            # Get count of existing references to this external ID
            reference_count = (
                self.session.query(Feed)
                .join(Externalid)
                .filter(
                    Externalid.associated_id == payload.external_id,
                    Externalid.source == payload.source,
                )
                .count()
            )

            # Create new feed with updated URL
            new_feed_id = str(uuid.uuid4())
            # Added counter to stable_id
            stable_id = (
                f"{payload.source}-{payload.external_id}"
                if reference_count == 1
                else f"{payload.source}-{payload.external_id}_{reference_count}"
            )

            log_message(
                "debug",
                f"Generated new stable_id: {stable_id} (reference count: {reference_count})",
            )

            # Create new feed entry
            new_feed = Feed(
                id=new_feed_id,
                data_type=payload.spec,
                producer_url=payload.feed_url,
                authentication_type=payload.type if payload.type else "0",
                authentication_info_url=payload.auth_info_url,
                api_key_parameter_name=payload.auth_param_name,
                stable_id=stable_id,
                status="active",
                provider=payload.operator_name,
                operational_status="wip",
            )

            # Add new feed to session
            self.session.add(new_feed)

            # Update old feed status to deprecated
            old_feed = self.session.get(Feed, old_feed_id)
            if old_feed:
                old_feed.status = "deprecated"
                log_message("debug", f"Deprecating old feed ID: {old_feed_id}")

            # Create new external ID mapping for updated feed
            new_external_id = Externalid(
                feed_id=new_feed_id,
                associated_id=payload.external_id,
                source=payload.source,
            )
            self.session.add(new_external_id)
            log_message(
                "debug", f"Created new external ID mapping for feed_id: {new_feed_id}"
            )

            # Create redirect
            redirect = Redirectingid(source_id=old_feed_id, target_id=new_feed_id)
            self.session.add(redirect)
            log_message(
                "debug", f"Created redirect from {old_feed_id} to {new_feed_id}"
            )

            # Create or get location and add to new feed
            location = create_or_get_location(
                self.session, payload.country, payload.state_province, payload.city_name
            )

            if location:
                new_feed.locations.append(location)
                log_message(
                    "debug", f"Added location information for feed: {new_feed_id}"
                )

            self.session.flush()

            log_message(
                "info",
                f"Updated feed for external_id: {payload.external_id}, new feed_id: {new_feed_id}",
            )

        except Exception as e:
            log_message(
                "error",
                f"Error updating feed for external_id {payload.external_id}: {str(e)}",
            )
            raise

    def check_feed_url_exists(self, feed_url: str) -> bool:
        """
        Check if a feed with the given URL exists in any state

        Args:
            feed_url (str): The URL to check

        Returns:
            bool: True if any feed with this URL exists and is active, or if URL exists in deprecated feed
        """
        result = self.session.query(Feed).filter(Feed.producer_url == feed_url).first()

        if result is not None:
            if result.status == "active":
                log_message(
                    "info", f"Found existing feed with URL: {feed_url} (status: active)"
                )
                return True
            elif result.status == "deprecated":
                log_message(
                    "error",
                    f"Feed URL {feed_url} exists in deprecated feed (id: {result.id}). "
                    "Cannot reuse URLs from deprecated feeds.",
                )
                return True

        log_message("debug", f"No existing feed found with URL: {feed_url}")
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
        result = (
            self.session.query(Feed)
            .filter(Feed.externalids.any(associated_id=external_id, source=source))
            .first()
        )
        if result is not None:
            log_message(
                "info",
                f"Retrieved feed {result.stable_id} "
                f"info for external_id: {external_id} (status: {result.status})",
            )
            return result.id, result.producer_url
        log_message("info", f"No existing feed found for external_id: {external_id}")
        return None, None

    def publish_to_batch_topic(self, payload: FeedPayload) -> None:
        """
        Publish feed to dataset batch topic

        Args:
            payload (FeedPayload): The feed payload to publish
        """
        topic_path = self.publisher.topic_path(PROJECT_ID, DATASET_BATCH_TOPIC)
        log_message("debug", f"Publishing to topic: {topic_path}")

        # Prepare message data in the expected format
        message_data = {
            "execution_id": payload.execution_id,
            "producer_url": payload.feed_url,
            "feed_stable_id": f"{payload.source}-{payload.external_id}",
            "feed_id": payload.feed_id,
            "dataset_id": None,
            "dataset_hash": None,
            "authentication_type": payload.type if payload.type else "0",
            "authentication_info_url": payload.auth_info_url,
            "api_key_parameter_name": payload.auth_param_name,
        }

        try:
            log_message("debug", f"Preparing to publish feed_id: {payload.feed_id}")
            # Convert to JSON string and encode as base64
            json_str = json.dumps(message_data)
            encoded_data = base64.b64encode(json_str.encode("utf-8"))

            future = self.publisher.publish(topic_path, data=encoded_data)
            future.result()
            log_message(
                "info", f"Published feed {payload.feed_id} to dataset batch topic"
            )
        except Exception as e:
            error_msg = f"Error publishing to dataset batch topic: {str(e)}"
            log_message("error", error_msg)
            raise


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

            log_message("info", f"Successfully processed feed: {payload.external_id}")
            return "Success", 200

        finally:
            close_db_session(db_session)

    except Exception as e:
        error_msg = f"Error processing feed event: {str(e)}"
        log_message("error", error_msg)
        return error_msg, 500
