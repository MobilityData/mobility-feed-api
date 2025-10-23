from unittest.mock import MagicMock
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Redirectingid,
    Externalid,
    Gtfsrealtimefeed,
    Entitytype,
)
from feeds_operations.impl.models.update_request_gtfs_rt_feed_impl import (
    UpdateRequestGtfsRtFeedImpl,
)
from feeds_gen.models.feed_status import FeedStatus
from feeds_gen.models.source_info import SourceInfo
from feeds_gen.models.update_request_gtfs_rt_feed import (
    UpdateRequestGtfsRtFeed,
)
from shared.db_models.external_id_impl import ExternalIdImpl
from shared.db_models.redirect_impl import RedirectImpl


def test_from_orm():
    redirecting_id = Redirectingid(target=MagicMock(stable_id="target_stable_id"))
    external_id = Externalid(associated_id="external_id")
    gtfs_feed = Gtfsrealtimefeed(
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

    result = UpdateRequestGtfsRtFeedImpl.from_orm(gtfs_feed)
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
    result = UpdateRequestGtfsRtFeedImpl.from_orm(None)
    assert result is None


def test_to_orm():
    update_request = UpdateRequestGtfsRtFeed(
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
        redirects=[RedirectImpl(target_id="target_stable_id", comment="Test comment")],
        external_ids=[ExternalIdImpl(external_id="external_id")],
        entity_types=["vp"],
        feed_references=["feed_reference"],
    )
    entity = Gtfsrealtimefeed(id="1", stable_id="stable_id", data_type="gtfs")
    target_feed = Gtfsfeed(id=2, stable_id="target_stable_id")
    resulting_entity = Entitytype(name="VP")

    session = MagicMock()
    session.query.return_value.filter.return_value.first.side_effect = [
        target_feed,
        resulting_entity,
    ]

    result = UpdateRequestGtfsRtFeedImpl.to_orm(update_request, entity, session)
    assert result is not None
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
    update_request = UpdateRequestGtfsRtFeed(
        id="stable_id",
        status=FeedStatus.ACTIVE,
        provider="provider",
        feed_name="feed_name",
        note="note",
        feed_contact_email="email@example.com",
        source_info=None,
        redirects=[RedirectImpl(target_id="target_stable_id", comment="Test comment")],
        external_ids=[ExternalIdImpl(external_id="external_id")],
        entity_types=["vp"],
        feed_references=["feed_reference"],
    )
    entity = Gtfsrealtimefeed(id="1", stable_id="stable_id", data_type="gtfs")
    target_feed = Gtfsfeed(id=2, stable_id="target_stable_id")

    session = MagicMock()
    session.query.return_value.filter.return_value.first.side_effect = [
        target_feed,
        None,
    ]

    result = UpdateRequestGtfsRtFeedImpl.to_orm(update_request, entity, session)

    assert result.producer_url is None
    assert result.authentication_type is None
    assert result.authentication_info_url is None
    assert result.api_key_parameter_name is None
    assert result.license_url is None
