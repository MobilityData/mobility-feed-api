# from unittest.mock import patch, Mock, MagicMock
# from main import backfill_datasets, backfill_dataset_service_date_range, is_version_gte
# from shared.database_gen.sqlacodegen_models import Gtfsdataset
# from test_shared.test_utils.database_utils import default_db_url

from unittest.mock import patch, MagicMock
from test_shared.test_utils.database_utils import default_db_url
from main import update_feed_status, update_feed_statuses_query
from datetime import date, timedelta

import os


def test_update_feed_status_return():
    mock_session = MagicMock()

    today = date(2025, 3, 1)

    mock_subquery = MagicMock()
    mock_subquery.c.feed_id = 1
    mock_subquery.c.service_date_range_start = today - timedelta(days=10)
    mock_subquery.c.service_date_range_end = today + timedelta(days=10)

    mock_query = mock_session.query.return_value
    mock_query.filter.return_value.subquery.return_value = mock_subquery

    mock_update_query = mock_session.query.return_value.filter.return_value
    mock_update_query.update.return_value = 3

    updated_count = update_feed_statuses_query(mock_session)

    assert updated_count == 3
    mock_session.commit.assert_called_once()


@patch("main.Logger", autospec=True)
@patch("main.update_feed_statuses_query")
def test_updated_feed_status(mock_update_query, mock_logger):
    mock_update_query.return_value = 5

    with patch.dict(os.environ, {"FEEDS_DATABASE_URL": default_db_url}):
        response_body, status_code = update_feed_status(None)

    mock_update_query.asser_called_once()
    assert response_body == "Script executed successfully. 5 feeds updated"
    assert status_code == 200


@patch("main.Logger", autospec=True)
@patch("main.update_feed_statuses_query")
def test_updated_feed_status_error_raised(mock_update_query, mock_logger):
    mock_update_query.side_effect = Exception("Mocked exception")

    with patch.dict(os.environ, {"FEEDS_DATABASE_URL": default_db_url}):
        response_body, status_code = update_feed_status(None)

    mock_update_query.asser_called_once()
    assert response_body == "Error updating the feed statuses: Mocked exception"
    assert status_code == 500
