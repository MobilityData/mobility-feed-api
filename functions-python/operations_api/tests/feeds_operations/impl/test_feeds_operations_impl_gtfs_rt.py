import os
from unittest import mock
from unittest.mock import patch

import pytest
from starlette.responses import Response

from database_gen.sqlacodegen_models import Gtfsrealtimefeed
from feeds_operations.impl.feeds_operations_impl import OperationsApiImpl
from feeds_operations_gen.models.authentication_type import AuthenticationType
from feeds_operations_gen.models.entity_type import EntityType
from feeds_operations_gen.models.feed_status import FeedStatus
from feeds_operations_gen.models.source_info import SourceInfo
from feeds_operations_gen.models.update_request_gtfs_rt_feed import (
    UpdateRequestGtfsRtFeed,
)
from operations_api.tests.conftest import feed_mdb_41
from test_utils.database_utils import get_testing_session, default_db_url


@pytest.fixture
def update_request_gtfs_rt_feed():
    return UpdateRequestGtfsRtFeed(
        id=feed_mdb_41.stable_id,
        status=FeedStatus(feed_mdb_41.status.lower()),
        external_ids=[],
        provider=feed_mdb_41.provider,
        feed_name=feed_mdb_41.feed_name,
        note=feed_mdb_41.note,
        feed_contact_email=feed_mdb_41.feed_contact_email,
        source_info=SourceInfo(
            producer_url=feed_mdb_41.producer_url,
            authentication_type=AuthenticationType(
                int(feed_mdb_41.authentication_type)
            ),
            authentication_info_url=feed_mdb_41.authentication_info_url,
            api_key_parameter_name=feed_mdb_41.api_key_parameter_name,
            license_url=feed_mdb_41.license_url,
        ),
        redirects=[],
        operational_status_action="no_change",
        entity_types=[EntityType.VP],
    )


@patch("helpers.logger.Logger")
@mock.patch.dict(
    os.environ,
    {
        "FEEDS_DATABASE_URL": default_db_url,
    },
)
@pytest.mark.asyncio
async def test_update_gtfs_feed_field_change(_, update_request_gtfs_rt_feed):
    update_request_gtfs_rt_feed.feed_name = "New feed name"
    with get_testing_session() as session:
        api = OperationsApiImpl()
        response: Response = await api.update_gtfs_rt_feed(update_request_gtfs_rt_feed)
        assert response.status_code == 200

        db_feed = (
            session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == feed_mdb_41.stable_id)
            .one()
        )
        assert db_feed.feed_name == "New feed name"


@patch("helpers.logger.Logger")
@mock.patch.dict(
    os.environ,
    {
        "FEEDS_DATABASE_URL": default_db_url,
    },
)
@pytest.mark.asyncio
async def test_update_gtfs_feed_static_change(_, update_request_gtfs_rt_feed):
    update_request_gtfs_rt_feed.feed_references = ["mdb-400"]
    with get_testing_session() as session:
        api = OperationsApiImpl()
        response: Response = await api.update_gtfs_rt_feed(update_request_gtfs_rt_feed)
        assert response.status_code == 200

        db_feed = (
            session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == feed_mdb_41.stable_id)
            .one()
        )
        assert len(db_feed.gtfs_feeds) == 1
        feed = next(
            (feed for feed in db_feed.gtfs_feeds if feed.stable_id == "mdb-400"), None
        )
        assert feed is not None, "Feed with stable ID 'mdb-400' not found"
