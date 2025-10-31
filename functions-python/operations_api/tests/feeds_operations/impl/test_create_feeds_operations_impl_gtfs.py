import pytest
from fastapi import HTTPException

from conftest import feed_mdb_40
from feeds_operations.impl.feeds_operations_impl import OperationsApiImpl
from feeds_gen.models.feed_status import FeedStatus
from feeds_gen.models.source_info import SourceInfo
from feeds_gen.models.update_request_gtfs_feed import UpdateRequestGtfsFeed
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import Gtfsfeed
from test_shared.test_utils.database_utils import default_db_url

# Add imports for create GTFS feed request models
from feeds_gen.models.operation_create_request_gtfs_feed import (
    OperationCreateRequestGtfsFeed,
)
from feeds_gen.models.operation_create_request_gtfs_feed_source_info import (
    OperationCreateRequestGtfsFeedSourceInfo,
)
import json
import uuid


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
            authentication_type=int(feed_mdb_40.authentication_type),
            authentication_info_url=feed_mdb_40.authentication_info_url,
            api_key_parameter_name=feed_mdb_40.api_key_parameter_name,
            license_url=feed_mdb_40.license_url,
        ),
        redirects=[],
        operational_status_action="no_change",
        official=True,
    )


@pytest.fixture
def db_session():
    # Provide a database session fixture
    db = Database(feeds_database_url=default_db_url)
    with db.start_db_session() as session:
        yield session


# -------------------------------
# Tests for create_gtfs_feed
# -------------------------------


@pytest.mark.asyncio
async def test_create_gtfs_feed_success(db_session):
    api = OperationsApiImpl()
    unique_url = f"https://new-feed.example.com/{uuid.uuid4()}"
    request = OperationCreateRequestGtfsFeed(
        # status can be omitted; include for completeness
        status=FeedStatus.ACTIVE,
        provider="New Provider",
        feed_name="New Feed",
        note="Test creation",
        feed_contact_email="contact@example.com",
        source_info=OperationCreateRequestGtfsFeedSourceInfo(
            producer_url=unique_url,
            authentication_type=0,
            authentication_info_url=None,
            api_key_parameter_name=None,
            license_url=None,
        ),
        operational_status="wip",
        official=True,
        redirects=[],
        external_ids=[],
        locations=[],
        related_links=[],
    )

    response = await api.create_gtfs_feed(request)
    assert response.status_code == 201

    payload = json.loads(response.body)
    try:
        # Parse response payload and verify DB persistence
        assert payload.get("id") and isinstance(payload["id"], str)
        assert payload.get("stable_id") and payload["stable_id"].startswith("md-")
        assert payload.get("data_type") == "gtfs"

        created = (
            db_session.query(Gtfsfeed)
            .filter(Gtfsfeed.stable_id == payload["stable_id"])
            .one()
        )
        assert created.id == payload["id"]
        assert created.data_type == "gtfs"
        assert created.provider == "New Provider"
        assert created.operational_status == "wip"
    finally:
        # Cleanup to avoid impacting other tests
        stable_id = payload.get("stable_id") if isinstance(payload, dict) else None
        if stable_id:
            created = (
                db_session.query(Gtfsfeed)
                .filter(Gtfsfeed.stable_id == stable_id)
                .one_or_none()
            )
            if created is not None:
                db_session.delete(created)
                db_session.commit()


@pytest.mark.asyncio
async def test_create_gtfs_feed_duplicate_url_rejected():
    api = OperationsApiImpl()
    # Use a URL that normalizes to the existing feed's producer_url (from feed_mdb_40)
    duplicate_url = " https://PRODUCER_URL/ "
    request = OperationCreateRequestGtfsFeed(
        status=FeedStatus.ACTIVE,
        provider="Dup Provider",
        feed_name="Dup Feed",
        note="Dup",
        feed_contact_email="dup@example.com",
        source_info=OperationCreateRequestGtfsFeedSourceInfo(
            producer_url=duplicate_url,
            authentication_type=0,
        ),
        operational_status="wip",
        official=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await api.create_gtfs_feed(request)

    assert exc_info.value.status_code == 400
    assert (
        exc_info.value.detail
        == f"A published feed with url {duplicate_url} already exists."
    )
