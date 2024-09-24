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

from dataclasses import dataclass
from typing import Any

from google.cloud.pubsub_v1.publisher.futures import Future
from sqlalchemy.orm import Session


@dataclass
class FeedSyncPayload:
    """
    Data class for feed sync payloads.
    """

    external_id: str
    payload: Any


class FeedSyncProcessor:
    """
    Abstract class for feed sync processors
    """

    def process_sync(self, session: Session, execution_id: str) -> list[FeedSyncPayload]:
        """
        Abstract method to process feed sync.
        :param session: database session
        :param execution_id: execution ID. This ID is used for logging and debugging purposes.
        :return: list of FeedSyncPayload
        """
        pass

    def publish_callback(
        self, future: Future, payload: FeedSyncPayload, topic_path: str
    ):
        """
        Abstract method for publishing callback.
        :param future: Future object
        :param payload: FeedSyncPayload object
        :param topic_path: Pub/Sub topic path
        """
        pass
