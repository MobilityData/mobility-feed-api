import os
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.responses import Response

from database_gen.sqlacodegen_models import Gtfsfeed
from feeds_operations.impl.feeds_operations_impl import OperationsApiImpl
from feeds_operations_gen.models.authentication_type import AuthenticationType
from feeds_operations_gen.models.feed_status import FeedStatus
from feeds_operations_gen.models.source_info import SourceInfo
from feeds_operations_gen.models.update_request_gtfs_feed import UpdateRequestGtfsFeed
from operations_api.tests.conftest import feed_mdb_40
from test_utils.database_utils import get_testing_session, default_db_url


@pytest.fixture
def update_request_gtfs_feed():
    return UpdateRequestGtfsFeed(
        id=feed_mdb_40.id,
        status=FeedStatus(feed_mdb_40.status.lower()),
        external_ids=[],
        provider=feed_mdb_40.provider,
        feed_name=feed_mdb_40.feed_name,
        note=feed_mdb_40.note,
        feed_contact_email=feed_mdb_40.feed_contact_email,
        source_info=SourceInfo(
            producer_url=feed_mdb_40.producer_url,
            authentication_type=AuthenticationType(
                int(feed_mdb_40.authentication_type)
            ),
            authentication_info_url=feed_mdb_40.authentication_info_url,
            api_key_parameter_name=feed_mdb_40.api_key_parameter_name,
            license_url=feed_mdb_40.license_url,
        ),
        redirects=[],
        operational_status_action="no_change",
    )


@patch("helpers.logger.Logger")
@mock.patch.dict(
    os.environ,
    {
        "FEEDS_DATABASE_URL": default_db_url,
    },
)
@pytest.mark.asyncio
async def test_update_gtfs_feed_no_changes(_, update_request_gtfs_feed):
    api = OperationsApiImpl()
    response: Response = await api.update_gtfs_feed(update_request_gtfs_feed)
    assert response.status_code == 204


@patch("helpers.logger.Logger")
@mock.patch.dict(
    os.environ,
    {
        "FEEDS_DATABASE_URL": default_db_url,
    },
)
@pytest.mark.asyncio
async def test_update_gtfs_feed_field_change(_, update_request_gtfs_feed):
    update_request_gtfs_feed.feed_name = "New feed name"
    with get_testing_session() as session:
        api = OperationsApiImpl()
        response: Response = await api.update_gtfs_feed(update_request_gtfs_feed)
        assert response.status_code == 200

        db_feed = (
            session.query(Gtfsfeed)
            .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
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
async def test_update_gtfs_feed_set_wip(_, update_request_gtfs_feed):
    update_request_gtfs_feed.operational_status_action = "wip"
    with get_testing_session() as session:
        api = OperationsApiImpl()
        response: Response = await api.update_gtfs_feed(update_request_gtfs_feed)
        assert response.status_code == 200

        db_feed = (
            session.query(Gtfsfeed)
            .filter(Gtfsfeed.stable_id == feed_mdb_40.stable_id)
            .one()
        )
        assert db_feed.operational_status == "wip"


@patch("helpers.logger.Logger")
@mock.patch.dict(
    os.environ,
    {
        "FEEDS_DATABASE_URL": default_db_url,
    },
)
@pytest.mark.asyncio
async def test_update_gtfs_feed_invalid_feed(_, update_request_gtfs_feed):
    update_request_gtfs_feed.id = "invalid"
    api = OperationsApiImpl()
    with pytest.raises(HTTPException) as exc_info:
        await api.update_gtfs_feed(update_request_gtfs_feed)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Feed ID not found: invalid"
