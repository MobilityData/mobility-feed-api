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
            downloaded_at=datetime(2023, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
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

    def test_to_orm_from_dict_none(self):
        """to_orm_from_dict returns None when input is None or empty dict."""
        assert FeedImpl.to_orm_from_dict(None) is None
        assert FeedImpl.to_orm_from_dict({}) is None

    def test_to_orm_from_dict_full_payload(self):
        """to_orm_from_dict maps primitives and nested collections; sorts externalids by associated_id."""
        now = datetime(2024, 5, 1, 12, 30, 0)
        updated = datetime(2024, 6, 1, 8, 0, 0)
        payload = {
            "id": "feed-123",
            "stable_id": "stable-123",
            "data_type": "gtfs",
            "created_at": now,
            "provider": "Provider A",
            "feed_contact_email": "contact@example.com",
            "producer_url": "https://producer.example.com",
            "authentication_type": 1,  # should be converted to string
            "authentication_info_url": "https://auth.example.com",
            "api_key_parameter_name": "api_key",
            "license_url": "https://license.example.com",
            "status": "active",
            "official": True,
            "official_updated_at": updated,
            "feed_name": "Feed Name",
            "note": "Some note",
            # avoid DB-dependent fields: locations and redirectingids
            "externalids": [
                {"external_id": "b-id", "source": "src"},
                {"external_id": "a-id", "source": "src"},
            ],
            "feedrelatedlinks": [
                {"code": "docs", "url": "https://docs.example.com", "description": "Docs"},
                {"code": "home", "url": "https://home.example.com", "description": "Home"},
            ],
        }

        obj = FeedImpl.to_orm_from_dict(payload)

        # Basic type
        assert isinstance(obj, Feed)

        # Primitives
        assert obj.id == "feed-123"
        assert obj.stable_id == "stable-123"
        assert obj.data_type == "gtfs"
        assert obj.created_at == now
        assert obj.provider == "Provider A"
        assert obj.feed_contact_email == "contact@example.com"
        assert obj.producer_url == "https://producer.example.com"
        # authentication_type coerced to string per implementation
        assert obj.authentication_type == "1"
        assert obj.authentication_info_url == "https://auth.example.com"
        assert obj.api_key_parameter_name == "api_key"
        assert obj.license_url == "https://license.example.com"
        assert obj.status == "active"
        assert obj.official is True
        assert obj.official_updated_at == updated
        assert obj.feed_name == "Feed Name"
        assert obj.note == "Some note"

        # Nested: externalids should be sorted by associated_id
        assert [type(e).__name__ for e in obj.externalids] == ["Externalid", "Externalid"]
        got_ext = [(e.source, e.associated_id) for e in obj.externalids]
        assert got_ext == [("src", "a-id"), ("src", "b-id")]

        # Nested: feedrelatedlinks preserved order (no explicit sort in impl)
        assert len(obj.feedrelatedlinks) == 2
        codes = [feedrelatedlinks.code for feedrelatedlinks in obj.feedrelatedlinks]
        urls = [feedrelatedlinks.url for feedrelatedlinks in obj.feedrelatedlinks]
        assert codes == ["docs", "home"]
        assert urls == ["https://docs.example.com", "https://home.example.com"]

        # Relationships not provided should be empty lists
        assert obj.redirectingids == []
        assert obj.locations == []

    def test_to_orm_from_dict_empty_collections(self):
        """Explicit empty lists yield empty relationship collections in ORM object."""
        payload = {
            "stable_id": "s",
            "data_type": "gtfs",
            "externalids": [],
            "feedrelatedlinks": [],
            "redirectingids": [],
            "locations": [],
        }
        obj = FeedImpl.to_orm_from_dict(payload)
        assert isinstance(obj, Feed)
        assert obj.externalids == []
        assert obj.feedrelatedlinks == []
        assert obj.redirectingids == []
        assert obj.locations == []
