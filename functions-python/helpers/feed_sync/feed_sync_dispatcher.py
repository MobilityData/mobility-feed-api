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

from helpers.database import start_db_session, close_db_session
from helpers.feed_sync.feed_sync_common import FeedSyncProcessor
from helpers.pub_sub import get_pubsub_client, publish


def feed_sync_dispatcher(
    feed_sync_processor: FeedSyncProcessor, pubsub_topic_path: str, execution_id: str
):
    """
    HTTP Function to process APIs feed syncs and publishes events to a Pub/Sub topic to be processed.
    :param pubsub_topic_path: name of the Pub/Sub topic to publish to
    :param execution_id: execution ID
    :param feed_sync_processor: FeedSync object
    :return: HTTP response object
    """
    publisher = get_pubsub_client()
    try:
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
        payloads = feed_sync_processor.process_sync(session, execution_id)
    except Exception as error:
        logging.error(f"Error processing feeds sync: {error}")
        raise Exception(f"Error processing feeds sync: {error}")
    finally:
        close_db_session(session)

    logging.info(f"Total feeds to add/update: {len(payloads)}.")

    for payload in payloads:
        data_str = json.dumps(payload.payload.__dict__)
        print(f"Publishing {data_str} to {pubsub_topic_path}.")
        future = publish(publisher, pubsub_topic_path, data_str.encode("utf-8"))
        future.add_done_callback(
            lambda _: feed_sync_processor.publish_callback(
                future, payload, pubsub_topic_path
            )
        )

    logging.info(
        f"Publish completed. Published {len(payloads)} feeds to {pubsub_topic_path}."
    )
