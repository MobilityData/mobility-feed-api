import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from shared.db_models.feed_impl import FeedImpl
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Externalid,
    Location,
    Gtfsdataset,
    Validationreport,
    Redirectingid,
    Feature,
)
from shared.db_models.external_id_impl import ExternalIdImpl
from shared.db_models.redirect_impl import RedirectImpl
from feeds_gen.models.source_info import SourceInfo

targetFeed = Feed(
    id="id1",
    stable_id="target_id",
    locations=[],
    externalids=[],
    gtfsdatasets=[],
    redirectingids=[],
)
feed_orm = Feed(
    id="id",
    data_type="gtfs",
    feed_name="feed_name",
    note="note",
    producer_url="producer_url",
    authentication_type="1",
    authentication_info_url="authentication_info_url",
    api_key_parameter_name="api_key_parameter_name",
    license_url="license_url",
    stable_id="stable_id",
    status="active",
    feed_contact_email="feed_contact_email",
    provider="provider",
    locations=[
        Location(
            id="id",
            country_code="CA",
            country=None,
            subdivision_name="subdivision_name",
            municipality="municipality",
        )
    ],
    externalids=[
        Externalid(
            feed_id="feed_id",
            associated_id="associated_id",
            source="source",
        )
    ],
    gtfsdatasets=[
        Gtfsdataset(
            id="id",
            stable_id="stable_id",
            feed_id="feed_id",
            hosted_url="hosted_url",
            note="note",
            downloaded_at="downloaded_at",
            hash="hash",
            bounding_box="bounding_box",
            service_date_range_start=datetime(2024, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("Canada/Atlantic")),
            service_date_range_end=datetime(2025, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("Canada/Atlantic")),
            agency_timezone="Canada/Atlantic",
            validation_reports=[
                Validationreport(
                    id="id",
                    validator_version="validator_version",
                    validated_at=datetime(year=2022, month=12, day=31, hour=13, minute=45, second=56),
                    html_report="html_report",
                    json_report="json_report",
                    features=[Feature(name="feature")],
                    notices=[],
                )
            ],
        )
    ],
    redirectingids=[
        Redirectingid(source_id="source_id", target_id="id1", redirect_comment="redirect_comment", target=targetFeed)
    ],
)

expected_base_feed_result = FeedImpl(
    id="stable_id",
    data_type="gtfs",
    status="active",
    external_ids=[ExternalIdImpl(external_id="associated_id", source="source")],
    provider="provider",
    feed_name="feed_name",
    note="note",
    feed_contact_email="feed_contact_email",
    related_links=[],
    source_info=SourceInfo(
        producer_url="producer_url",
        authentication_type=1,
        authentication_info_url="authentication_info_url",
        api_key_parameter_name="api_key_parameter_name",
        license_url="license_url",
    ),
    redirects=[
        RedirectImpl(
            target_id="target_id",
            comment="redirect_comment",
        )
    ],
)


class TestBasicFeedImpl(unittest.TestCase):
    """Test the `BasicFeedImpl` model."""

    def test_from_orm_all_fields(self):
        """Test the `from_orm` method with all fields."""
        result = FeedImpl.from_orm(feed_orm)
        assert result == expected_base_feed_result

    def test_from_orm_empty_fields(self):
        """Test the `from_orm` method with not provided fields."""
        # Test with empty fields and None values
        # No error should be raised
        # Target is set to None as deep copy is failing for unknown reasons
        # At the end of the test, the target is set back to the original value
        feed_orm.redirectingids[0].target = None
        target_feed_orm = copy.deepcopy(feed_orm)
        target_feed_orm.feed_name = ""
        target_feed_orm.provider = None
        target_feed_orm.externalids = []
        target_feed_orm.redirectingids = []

        target_expected_base_feed_result = copy.deepcopy(expected_base_feed_result)
        target_expected_base_feed_result.feed_name = ""
        target_expected_base_feed_result.provider = None
        target_expected_base_feed_result.external_ids = []
        target_expected_base_feed_result.redirects = []

        result = FeedImpl.from_orm(target_feed_orm)
        assert result == target_expected_base_feed_result

        # Test all None values
        # No error should be raised
        # Resulting list must be empty and not None
        empty_feed_orm = Feed()
        expected_empty_feed = FeedImpl(
            external_ids=[],
            redirects=[],
            source_info=SourceInfo(),
            related_links=[],
        )
        empty_result = FeedImpl.from_orm(empty_feed_orm)
        assert empty_result == expected_empty_feed
        # Setting the target at the end of the test
        feed_orm.redirectingids[0].target = targetFeed

    def test_from_orm_none(self):
        """Test the `from_orm` method with None."""
        assert FeedImpl.from_orm(None) is None
