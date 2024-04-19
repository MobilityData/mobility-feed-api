import pytest
import unittest
import copy
from faker import Faker

from feeds.impl.models.search_feeds200_response_results_inner_impl import SearchFeeds200ResponseResultsInnerImpl
from feeds_gen.models.latest_dataset import LatestDataset
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
    external_ids=[],
    redirect_ids=[],
    feed_reference_ids=[],
    entities=["sa"],
    locations=[],
)


class TestSearchFeeds200ResponseResultsInnerImpl(unittest.TestCase):
    def test_from_orm_gtfs(self):
        item = copy.deepcopy(search_item)
        item.data_type = "gtfs"
        result = SearchFeeds200ResponseResultsInnerImpl.from_orm_gtfs(item)
        assert result.data_type == "gtfs"
        expected = SearchFeeds200ResponseResultsInnerImpl(
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
            latest_dataset=LatestDataset(
                id=item.latest_dataset_id,
                hosted_url=item.latest_dataset_hosted_url,
                downloaded_at=item.latest_dataset_downloaded_at,
                hash=item.latest_dataset_hash,
            ),
        )
        assert result == expected

    def test_from_orm_gtfs_rt(self):
        item = copy.deepcopy(search_item)
        item.data_type = "gtfs_rt"
        result = SearchFeeds200ResponseResultsInnerImpl.from_orm_gtfs_rt(item)
        assert result.data_type == "gtfs_rt"
        expected = SearchFeeds200ResponseResultsInnerImpl(
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
        )
        assert result == expected

    def test_from_orm(self):
        item = copy.deepcopy(search_item)
        item.data_type = "gtfs"
        result = SearchFeeds200ResponseResultsInnerImpl.from_orm(item)
        assert result.data_type == "gtfs"

        item = copy.deepcopy(search_item)
        item.data_type = "gtfs_rt"
        result = SearchFeeds200ResponseResultsInnerImpl.from_orm(item)
        assert result.data_type == "gtfs_rt"

        assert SearchFeeds200ResponseResultsInnerImpl.from_orm(None) is None

        with pytest.raises(ValueError):
            item = copy.deepcopy(search_item)
            item.data_type = "unknown"
            SearchFeeds200ResponseResultsInnerImpl.from_orm(item)
