#
#   MobilityData 2023
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
from unittest import mock
from unittest.mock import Mock, patch
from batch_datasets.src.main import get_active_feeds, batch_datasets
from test_utils.database_utils import get_testing_session, default_db_url


def test_get_active_feeds():
    with get_testing_session() as session:
        active_feeds = get_active_feeds(session)
        assert len(active_feeds) == 3
        #         assert all active feeds has authentication_type == '0'
        for feed in active_feeds:
            assert feed.authentication_type == "0"


@mock.patch.dict(
    os.environ,
    {"FEEDS_DATABASE_URL": default_db_url, "FEEDS_PUBSUB_TOPIC_NAME": "test_topic"},
)
@patch("batch_datasets.src.main.publish")
@patch("google.cloud.pubsub_v1.PublisherClient")
def test_batch_datasets(mock_client, mock_publish):
    with get_testing_session() as session:
        active_feeds = get_active_feeds(session)
        with patch(
            "dataset_service.main.BatchExecutionService.__init__", return_value=None
        ):
            with patch(
                "dataset_service.main.BatchExecutionService.save", return_value=None
            ):
                batch_datasets(Mock())
                assert mock_publish.call_count == 3
                # loop over mock_publish.call_args_list and check that the stable_id of the feed is in the list of
                # active feeds
                for i in range(3):
                    message = json.loads(
                        mock_publish.call_args_list[i][0][1].decode("utf-8")
                    )
                    assert message["feed_stable_id"] in [
                        feed.stable_id for feed in active_feeds
                    ]
