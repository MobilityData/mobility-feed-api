from unittest.mock import Mock, MagicMock

from feeds_operations.impl.models.operation_redirect_impl import OperationRedirectImpl
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Redirectingid, Externalid
from feeds_gen.models.feed_status import FeedStatus
from feeds_gen.models.source_info import SourceInfo
from feeds_gen.models.update_request_gtfs_feed import UpdateRequestGtfsFeed
from feeds_operations.impl.models.update_request_gtfs_feed_impl import (
    UpdateRequestGtfsFeedImpl,
)
from shared.db_models.external_id_impl import ExternalIdImpl


def test_from_orm():
    redirecting_id = Redirectingid(target=MagicMock(stable_id="target_stable_id"))
    external_id = Externalid(associated_id="external_id")
    gtfs_feed = Gtfsfeed(
        stable_id="stable_id",
        status="active",
        provider="provider",
        feed_name="feed_name",
        note="note",
        feed_contact_email="email@example.com",
        producer_url="http://producer.url",
        authentication_type=1,
        authentication_info_url="http://auth.info.url",
        api_key_parameter_name="api_key",
        license_url="http://license.url",
        redirectingids=[redirecting_id],
        externalids=[external_id],
    )

    result = UpdateRequestGtfsFeedImpl.from_orm(gtfs_feed)
    assert result.id == "stable_id"
    assert result.status == "active"
    assert result.provider == "provider"
    assert result.feed_name == "feed_name"
    assert result.note == "note"
    assert result.feed_contact_email == "email@example.com"
    assert result.source_info.producer_url == "http://producer.url"
    assert result.source_info.authentication_type == 1
    assert result.source_info.authentication_info_url == "http://auth.info.url"
    assert result.source_info.api_key_parameter_name == "api_key"
    assert result.source_info.license_url == "http://license.url"
    assert len(result.redirects) == 1
    assert result.redirects[0].target_id == "target_stable_id"
    assert len(result.external_ids) == 1
    assert result.external_ids[0].external_id == "external_id"


def test_from_orm_none():
    result = UpdateRequestGtfsFeedImpl.from_orm(None)
    assert result is None


def test_to_orm():
    update_request = UpdateRequestGtfsFeed(
        id="stable_id",
        status=FeedStatus.ACTIVE,
        provider="provider",
        feed_name="feed_name",
        note="note",
        feed_contact_email="email@example.com",
        source_info=SourceInfo(
            producer_url="http://producer.url",
            authentication_type=1,
            authentication_info_url="http://auth.info.url",
            api_key_parameter_name="api_key",
            license_url="http://license.url",
        ),
        redirects=[
            OperationRedirectImpl(target_id="target_stable_id", comment="Test comment")
        ],
        external_ids=[ExternalIdImpl(external_id="external_id")],
    )
    entity = Gtfsfeed(id="1", stable_id="stable_id", data_type="gtfs")
    target_feed = Gtfsfeed(id=2, stable_id="target_stable_id")
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = target_feed

    result = UpdateRequestGtfsFeedImpl.to_orm(update_request, entity, session)
    assert result.status == "active"
    assert result.provider == "provider"
    assert result.feed_name == "feed_name"
    assert result.note == "note"
    assert result.feed_contact_email == "email@example.com"
    assert result.producer_url == "http://producer.url"
    assert result.authentication_type == "1"
    assert result.authentication_info_url == "http://auth.info.url"
    assert result.api_key_parameter_name == "api_key"
    assert result.license_url == "http://license.url"
    assert len(result.redirectingids) == 1
    assert result.redirectingids[0].target_id == target_feed.id
    assert len(result.externalids) == 1
    assert result.externalids[0].associated_id == "external_id"


def test_to_orm_invalid_source_info():
    update_request = UpdateRequestGtfsFeed(
        id="stable_id",
        status=FeedStatus.ACTIVE,
        provider="provider",
        feed_name="feed_name",
        note="note",
        feed_contact_email="email@example.com",
        source_info=None,
        redirects=[
            OperationRedirectImpl(target_id="target_stable_id", comment="Test comment")
        ],
        external_ids=[ExternalIdImpl(external_id="external_id")],
    )
    entity = Gtfsfeed(id="id")
    session = Mock()

    result = UpdateRequestGtfsFeedImpl.to_orm(update_request, entity, session)
    assert result.producer_url is None
    assert result.authentication_type is None
    assert result.authentication_info_url is None
    assert result.api_key_parameter_name is None
    assert result.license_url is None
