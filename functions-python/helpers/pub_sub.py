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
import uuid

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1 import PublisherClient
from google.cloud.pubsub_v1.publisher.futures import Future


def get_pubsub_client():
    """
    Returns a Pub/Sub client.
    """
    return pubsub_v1.PublisherClient()


def publish(publisher: PublisherClient, topic_path: str, data_bytes: bytes) -> Future:
    """
    Publishes the given data to the Pub/Sub topic.
    """
    return publisher.publish(topic_path, data=data_bytes)


def get_execution_id(request, prefix: str) -> str:
    """
    Returns the execution ID for the request if available, otherwise generates a new one.
    @param request: HTTP request object
    @param prefix: prefix for the execution ID. Example: "batch-datasets"
    """
    trace_id = request.headers.get("X-Cloud-Trace-Context")
    execution_id = f"{prefix}-{trace_id}" if trace_id else f"{prefix}-{uuid.uuid4()}"
    return execution_id
