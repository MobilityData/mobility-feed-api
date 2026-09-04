from unittest.mock import patch, MagicMock

from sqlalchemy import column, func

from shared.database.database import with_db_session
from test_shared.test_utils.database_utils import default_db_url
from main import (
    update_feed_status,
    update_feed_statuses_query,
)
from shared.database_gen.sqlacodegen_models import Feed, Gtfsdataset, Gtfsfeed
from datetime import datetime, timezone
from typing import Iterator, NamedTuple
from uuid import uuid4

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
def test_null_service_date_range_sets_feed_inactive(db_session: Session) -> None:
    feed_id = str(uuid4())
    dataset_id = str(uuid4())
    stable_id = f"issue-1209-{uuid4()}"

    feed = Gtfsfeed(
        id=feed_id,
        stable_id=stable_id,
        status="active",
    )
    try:
        db_session.add(feed)
        db_session.flush()

        dataset = Gtfsdataset(
            id=dataset_id,
            stable_id=f"{stable_id}-dataset",
            feed=feed,
            downloaded_at=datetime.now(timezone.utc),
            service_date_range_start=None,
            service_date_range_end=None,
        )
        db_session.add(dataset)
        db_session.flush()

        feed.latest_dataset_id = dataset.id
        db_session.flush()

        with patch("shared.helpers.feed_status.create_refresh_materialized_view_task"):
            result = dict(update_feed_statuses_query(db_session, [stable_id]))

        db_session.expire_all()

        updated_feed = (
            db_session.query(Gtfsfeed).filter(Gtfsfeed.stable_id == stable_id).one()
        )

        assert result == {
            "inactive": 1,
            "active": 0,
            "future": 0,
        }
        assert updated_feed.status == "inactive"
    finally:
        db_session.rollback()


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

    class Columns:
        feed_id = column("feed_id")
        service_date_range_start = column("service_date_range_start")
        service_date_range_end = column("service_date_range_end")

    mock_subquery = MagicMock()
    mock_subquery.c = Columns()

    mock_query = mock_session.query.return_value
    mock_query.join.return_value.subquery.return_value = mock_subquery

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
