import pytest
import unittest
import copy
from faker import Faker

from shared.db_models.search_feed_item_result_impl import SearchFeedItemResultImpl
from feeds_gen.models.latest_dataset import LatestDataset
from feeds_gen.models.latest_dataset_validation_report import LatestDatasetValidationReport
from feeds_gen.models.location import Location
from feeds_gen.models.source_info import SourceInfo

fake = Faker()
downloaded_at = fake.date_time_this_month()


class FeedSearchRow:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


search_item = FeedSearchRow(
    feed_id="feed_id",
    feed_stable_id="feed_stable_id",
    data_type="gtfs",
    status="active",
    feed_name="feed_name",
    official=None,
    created_at=fake.date_time_this_month(),
    note="note",
    feed_contact_email="feed_contact_email",
    producer_url="producer_url",
    authentication_info_url="authentication_info_url",
    authentication_type=1,
    api_key_parameter_name="api_key_parameter_name",
    license_url="license_url",
    country_code="country_code",
    subdivision_name="subdivision_name",
    municipality="municipality",
    provider="provider",
    latest_dataset_id="latest_dataset_id",
    latest_dataset_hosted_url="latest_dataset_hosted_url",
    latest_dataset_downloaded_at=downloaded_at,
    latest_dataset_bounding_box=None,
    latest_dataset_hash="latest_dataset_hash",
    latest_dataset_service_date_range_start="2030-09-29T00:00:00+00:00",
    latest_dataset_service_date_range_end="2031-09-29T00:00:00+00:00",
    latest_dataset_agency_timezone="Canada/Atlantic",
    latest_total_error=1,
    latest_total_warning=2,
    latest_total_info=3,
    latest_unique_error_count=1,
    latest_unique_warning_count=2,
    latest_unique_info_count=3,
    latest_dataset_features=["feature1", "feature2"],
    external_ids=[],
    redirect_ids=[],
    feed_reference_ids=[],
    entities=["sa"],
    locations=[],
    country_translations=[],
    subdivision_name_translations=[],
    municipality_translations=[],
)


class TestSearchFeeds200ResponseResultsInnerImpl(unittest.TestCase):
    def test_from_orm_gtfs(self):
        item = copy.deepcopy(search_item)
        item.data_type = "gtfs"
        result = SearchFeedItemResultImpl.from_orm_gtfs(item)
        assert result.data_type == "gtfs"
        expected = SearchFeedItemResultImpl(
            id=item.feed_stable_id,
            data_type=item.data_type,
            status=item.status,
            external_ids=item.external_ids,
            provider=item.provider,
            feed_name=item.feed_name,
            note=item.note,
            feed_contact_email=item.feed_contact_email,
            source_info=SourceInfo(
                producer_url=item.producer_url,
                authentication_type=int(item.authentication_type) if item.authentication_type else None,
                authentication_info_url=item.authentication_info_url,
                api_key_parameter_name=item.api_key_parameter_name,
                license_url=item.license_url,
            ),
            redirects=item.redirect_ids,
            locations=item.locations,
            created_at=item.created_at,
            latest_dataset=LatestDataset(
                id=item.latest_dataset_id,
                hosted_url=item.latest_dataset_hosted_url,
                downloaded_at=item.latest_dataset_downloaded_at,
                hash=item.latest_dataset_hash,
                service_date_range_start=item.latest_dataset_service_date_range_start,
                service_date_range_end=item.latest_dataset_service_date_range_end,
                agency_timezone=item.latest_dataset_agency_timezone,
                validation_report=LatestDatasetValidationReport(
                    total_error=item.latest_total_error,
                    total_warning=item.latest_total_warning,
                    total_info=item.latest_total_info,
                    unique_error_count=item.latest_unique_error_count,
                    unique_warning_count=item.latest_unique_warning_count,
                    unique_info_count=item.latest_unique_info_count,
                    features=item.latest_dataset_features,
                ),
            ),
        )
        assert result == expected

    def test_from_orm_gtfs_rt(self):
        item = copy.deepcopy(search_item)
        item.data_type = "gtfs_rt"
        result = SearchFeedItemResultImpl.from_orm_gtfs_rt(item)
        assert result.data_type == "gtfs_rt"
        expected = SearchFeedItemResultImpl(
            id=item.feed_stable_id,
            data_type=item.data_type,
            status=item.status,
            external_ids=item.external_ids,
            provider=item.provider,
            feed_name=item.feed_name,
            note=item.note,
            feed_contact_email=item.feed_contact_email,
            source_info=SourceInfo(
                producer_url=item.producer_url,
                authentication_type=int(item.authentication_type) if item.authentication_type else None,
                authentication_info_url=item.authentication_info_url,
                api_key_parameter_name=item.api_key_parameter_name,
                license_url=item.license_url,
            ),
            redirects=item.redirect_ids,
            locations=item.locations,
            entity_types=item.entities,
            feed_references=item.feed_reference_ids,
            created_at=item.created_at,
        )
        assert result == expected

    def test_from_orm(self):
        item = copy.deepcopy(search_item)
        item.data_type = "gtfs"
        result = SearchFeedItemResultImpl.from_orm(item)
        assert result.data_type == "gtfs"

        item = copy.deepcopy(search_item)
        item.data_type = "gtfs_rt"
        result = SearchFeedItemResultImpl.from_orm(item)
        assert result.data_type == "gtfs_rt"

        assert SearchFeedItemResultImpl.from_orm(None) is None

        with pytest.raises(ValueError):
            item = copy.deepcopy(search_item)
            item.data_type = "unknown"
            SearchFeedItemResultImpl.from_orm(item)

    def test_from_orm_locations_country_provided(self):
        """Test that the country is not replaced with the translation."""
        item = copy.deepcopy(search_item)
        item.data_type = "gtfs"
        item.locations = [
            {
                "country_code": "CA",
                "country": "CanadaNotReplaced",
                "subdivision_name": "subdivision_name",
                "municipality": "municipality",
            }
        ]
        result = SearchFeedItemResultImpl.from_orm(item)
        assert result.data_type == "gtfs"
        assert result.locations == [
            Location(
                country_code="CA",
                country="CanadaNotReplaced",
                subdivision_name="subdivision_name",
                municipality="municipality",
            )
        ]

    def test_from_orm_locations_country_missing(self):
        """Test that the country is not replaced with the translation."""
        item = copy.deepcopy(search_item)
        item.data_type = "gtfs"
        item.locations = [
            {
                "country_code": "CA",
                "country": "",
                "subdivision_name": "subdivision_name",
                "municipality": "municipality",
            }
        ]
        result = SearchFeedItemResultImpl.from_orm(item)
        assert result.data_type == "gtfs"
        assert result.locations == [
            Location(
                country_code="CA", country="Canada", subdivision_name="subdivision_name", municipality="municipality"
            )
        ]

    def test_from_orm_locations_country_invalid_code(self):
        """Test that the country is not replaced with the translation."""
        item = copy.deepcopy(search_item)
        item.data_type = "gtfs"
        item.locations = [
            {
                "country_code": "XY",
                "country": "",
                "subdivision_name": "subdivision_name",
                "municipality": "municipality",
            }
        ]
        result = SearchFeedItemResultImpl.from_orm(item)
        assert result.data_type == "gtfs"
        assert result.locations == [
            Location(country_code="XY", country="", subdivision_name="subdivision_name", municipality="municipality")
        ]
