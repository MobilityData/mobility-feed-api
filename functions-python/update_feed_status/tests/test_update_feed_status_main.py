from unittest.mock import patch, MagicMock

from sqlalchemy import func

from shared.database.database import with_db_session
from shared.helpers.src.shared.database_gen.sqlacodegen_models import Gtfsfeed
from test_shared.test_utils.database_utils import default_db_url
from main import (
    update_feed_status,
    update_feed_statuses_query,
)
from shared.database_gen.sqlacodegen_models import Feed, Gtfsdataset
from datetime import date, timedelta
from typing import Iterator, NamedTuple

import os

from sqlalchemy.orm import Session


class PartialFeed(NamedTuple):
    """
    Subset of the Feed entity with only the fields queried in `fetch_feeds`.
    """

    id: str
    status: str


def fetch_feeds(session: Session) -> Iterator[PartialFeed]:
    # When adding or removing fields here, `PartialFeed` should be updated to
    # match, for type safety.
    query = session.query(Feed.id, Feed.status).filter(
        Feed.status != "deprecated",
        Feed.status != "development",
    )
    for feed in query:
        yield PartialFeed(id=feed.id, status=feed.status)


@with_db_session(db_url=default_db_url)
def test_update_feed_status(db_session: Session) -> None:
    result = (
        db_session.query(Gtfsfeed.status, func.count(Gtfsfeed.id))
        .join(Gtfsdataset, Gtfsfeed.latest_dataset_id == Gtfsdataset.id)
        .filter(
            Gtfsdataset.service_date_range_start.isnot(None),
            Gtfsdataset.service_date_range_end.isnot(None),
        )
        .group_by(Feed.status)
        .all()
    )
    print(dict(result))
    print("----------------------------------------------")
    feeds_before: dict[str, PartialFeed] = {f.id: f for f in fetch_feeds(db_session)}
    result = dict(update_feed_statuses_query(db_session, []))
    assert result == {
        "inactive": 3,
        "active": 2,
        "future": 1,
    }

    feeds_after: dict[str, PartialFeed] = {f.id: f for f in fetch_feeds(db_session)}
    expected_status_changes = {
        "2": "active",
        "7": "inactive",
        "8": "inactive",
        "10": "future",
        "22": "inactive",
        "25": "active",
    }
    for feed_id, feed_before in feeds_before.items():
        feed_after = feeds_after[feed_id]
        assert feed_after.status == expected_status_changes.get(
            feed_id, feed_before.status
        )


@with_db_session(db_url=default_db_url)
def test_update_feed_status_with_ids(db_session: Session) -> None:
    # clean_testing_db()
    # populate_database()
    feeds_before: dict[str, PartialFeed] = {f.id: f for f in fetch_feeds(db_session)}
    result = dict(update_feed_statuses_query(db_session, ["mdb-8"]))
    assert result == {
        "inactive": 1,
        "active": 0,
        "future": 0,
    }

    feeds_after: dict[str, PartialFeed] = {f.id: f for f in fetch_feeds(db_session)}
    expected_status_changes = {
        "8": "inactive",
    }
    for feed_id, feed_before in feeds_before.items():
        feed_after = feeds_after[feed_id]
        assert feed_after.status == expected_status_changes.get(
            feed_id, feed_before.status
        )


def test_update_feed_status_failed_query():
    mock_session = MagicMock()

    today = date(2025, 3, 1)

    class Columns:
        feed_id = 1
        service_date_range_start = today - timedelta(days=10)
        service_date_range_end = today + timedelta(days=10)

    mock_subquery = MagicMock()
    mock_subquery.c = Columns()
    # mock_subquery.c.feed_id = 1
    # mock_subquery.c.service_date_range_start = today - timedelta(days=10)
    # mock_subquery.c.service_date_range_end = today + timedelta(days=10)

    mock_query = mock_session.query.return_value
    mock_query.join.return_value.filter.return_value.subquery.return_value = (
        mock_subquery
    )

    mock_update_query = mock_session.query.return_value.filter.return_value
    mock_update_query.update.side_effect = Exception("Mocked exception")

    try:
        update_feed_statuses_query(mock_session, [])
    except Exception as e:
        assert str(e) == "Error updating feed statuses: Mocked exception"


@patch("main.update_feed_statuses_query")
def test_updated_feed_status(mock_update_query):
    return_value = {"active": 5}
    mock_update_query.return_value = return_value

    with patch.dict(os.environ, {"FEEDS_DATABASE_URL": default_db_url}):
        response_body, status_code = update_feed_status(None)

    mock_update_query.assert_called_once()
    assert response_body == return_value
    assert status_code == 200


@patch("main.update_feed_statuses_query")
def test_updated_feed_status_error_raised(mock_update_query):
    mock_update_query.side_effect = Exception("Mocked exception")

    with patch.dict(os.environ, {"FEEDS_DATABASE_URL": default_db_url}):
        response_body, status_code = update_feed_status(None)

    mock_update_query.assert_called_once()
    assert response_body == "Error updating the feed statuses: Mocked exception"
    assert status_code == 500
