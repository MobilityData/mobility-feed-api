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
import pytest
from unittest.mock import Mock, patch, MagicMock
from main import get_non_deprecated_feeds, batch_datasets
from shared.database.database import with_db_session
from test_shared.test_utils.database_utils import default_db_url


@with_db_session(db_url=default_db_url)
def test_get_non_deprecated_feeds(db_session):
    feeds = get_non_deprecated_feeds(db_session)
    assert len(feeds) == 10
    assert len([feed for feed in feeds if feed.status == "active"]) == 3
    assert len([feed for feed in feeds if feed.status == "inactive"]) == 7


@mock.patch.dict(
    os.environ,
    {
        "FEEDS_DATABASE_URL": default_db_url,
        "FEEDS_PUBSUB_TOPIC_NAME": "test_topic",
        "ENVIRONMENT": "test",
        "FEEDS_LIMIT": "5",
    },
)
@patch("main.publish")
@patch("main.get_pubsub_client")
@with_db_session(db_url=default_db_url)
def test_batch_datasets(mock_client, mock_publish, db_session):
    mock_client.return_value = MagicMock()
    feeds = get_non_deprecated_feeds(db_session)
    with patch(
        "shared.dataset_service.main.BatchExecutionService.__init__",
        return_value=None,
    ):
        with patch(
            "shared.dataset_service.main.BatchExecutionService.save",
            return_value=None,
        ):
            batch_datasets(Mock())
            assert mock_publish.call_count == 5
            # loop over mock_publish.call_args_list and check that the stable_id of the feed is in the list of
            # active feeds
            for i in range(3):
                message = json.loads(
                    mock_publish.call_args_list[i][0][2].decode("utf-8")
                )
                assert message["feed_stable_id"] in [feed.stable_id for feed in feeds]


def test_batch_datasets_exception():
    exception_message = "Failure occurred"
    mock_session = MagicMock()
    mock_session.side_effect = Exception(exception_message)

    with pytest.raises(Exception) as exec_info:
        batch_datasets(Mock(), mock_session)

        assert str(exec_info.value) == exception_message
