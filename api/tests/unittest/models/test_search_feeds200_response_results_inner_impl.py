import pytest
import unittest
import copy
from faker import Faker

from feeds.impl.models.search_feeds200_response_results_inner_impl import SearchFeeds200ResponseResultsInnerImpl
from feeds_gen.models.latest_dataset import LatestDataset
from feeds_gen.models.source_info import SourceInfo

# id: Optional[str] = Field(alias="id", default=None)
# data_type: Optional[str] = Field(alias="data_type", default=None)
# status: Optional[str] = Field(alias="status", default=None)
# external_ids: Optional[List[ExternalId]] = Field(alias="external_ids", default=None)
# provider: Optional[str] = Field(alias="provider", default=None)
# feed_name: Optional[str] = Field(alias="feed_name", default=None)
# note: Optional[str] = Field(alias="note", default=None)
# feed_contact_email: Optional[str] = Field(alias="feed_contact_email", default=None)
# source_info: Optional[SourceInfo] = Field(alias="source_info", default=None)
# redirects: Optional[List[Redirect]] = Field(alias="redirects", default=None)
# locations: Optional[List[Location]] = Field(alias="locations", default=None)
# latest_dataset: Optional[LatestDataset] = Field(alias="latest_dataset", default=None)
# entity_types: Optional[List[str]] = Field(alias="entity_types", default=None)
# feed_references: Optional[List[str]] = Field(alias="feed_references", default=None)

# Column('feed_stable_id', String(255), index=True),
# Column('feed_id', String(255)),
# Column('data_type', Enum('gtfs', 'gtfs_rt', name='datatype'), index=True),
# Column('status', Enum('active', 'inactive', 'development', 'deprecated', name='status'), index=True),
# Column('feed_name', String(255)),
# Column('note', String(255)),
# Column('feed_contact_email', String(255)),
# Column('producer_url', String(255)),
# Column('authentication_info_url', String(255)),
# Column('authentication_type', Enum('0', '1', '2', name='authenticationtype')),
# Column('api_key_parameter_name', String(255)),
# Column('license_url', String(255)),
# Column('country_code', String(3)),
# Column('subdivision_name', String(255)),
# Column('municipality', String(255)),
# Column('provider', Text),
# Column('latest_dataset_id', String(255)),
# Column('latest_dataset_hosted_url', String(255)),
# Column('latest_dataset_downloaded_at', DateTime),
# Column('latest_dataset_bounding_box',
#        Geometry('POLYGON', 4326, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry')),
# Column('latest_dataset_hash', String(255)),
# Column('external_ids', JSON),
# Column('redirect_ids', JSON),
# Column('feed_reference_ids', ARRAY(String())),
# Column('entities', ARRAY(String())),
# Column('locations', JSON),

fake = Faker()

downloaded_at = fake.date_time_this_month()


class FeedSearchRow:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# id = feed_search_row.feed_stable_id,
#
# provider = feed_search_row.provider,
# feed_name = feed_search_row.feed_name,
# note = feed_search_row.note,
# feed_contact_email = feed_search_row.feed_contact_email,
#
# source_info = SourceInfo(producer_url=feed_search_row.producer_url,
#                          authentication_type=feed_search_row.authentication_type,
#                          authentication_info_url=feed_search_row.authentication_info_url,
#                          api_key_parameter_name=feed_search_row.api_key_parameter_name,
#                          license_url=feed_search_row.license_url),
# redirects = feed_search_row.redirect_ids,
# locations = feed_search_row.locations,
# latest_dataset = LatestDataset(id=feed_search_row.latest_dataset_id,
#                                hosted_url=feed_search_row.latest_dataset_hosted_url,
#                                downloaded_at=feed_search_row.latest_dataset_downloaded_at,
#                                hash=feed_search_row.latest_dataset_hash) if feed_search_row.latest_dataset_id else None,

search_item = FeedSearchRow(
    feed_id='feed_id',
    feed_stable_id='feed_stable_id',
    data_type='gtfs',
    status='status',
    feed_name='feed_name',
    note='note',
    feed_contact_email='feed_contact_email',
    producer_url='producer_url',
    authentication_info_url='authentication_info_url',
    authentication_type=1,
    api_key_parameter_name='api_key_parameter_name',
    license_url='license_url',
    country_code='country_code',
    subdivision_name='subdivision_name',
    municipality='municipality',
    provider='provider',
    latest_dataset_id='latest_dataset_id',
    latest_dataset_hosted_url='latest_dataset_hosted_url',
    latest_dataset_downloaded_at=downloaded_at,
    latest_dataset_bounding_box=None,
    latest_dataset_hash='latest_dataset_hash',
    external_ids=[],
    redirect_ids=[],
    feed_reference_ids=[],
    entities=['ec'],
    locations=[],
)


class TestSearchFeeds200ResponseResultsInnerImpl(unittest.TestCase):

    def test_from_orm_gtfs(self):
        item = copy.deepcopy(search_item)
        item.data_type = 'gtfs'
        result = SearchFeeds200ResponseResultsInnerImpl.from_orm_gtfs(item)
        assert result.data_type == 'gtfs'
        expected = SearchFeeds200ResponseResultsInnerImpl(
            id=item.feed_stable_id,
            data_type=item.data_type,
            status=item.status,
            external_ids=item.external_ids,
            provider=item.provider,
            feed_name=item.feed_name,
            note=item.note,
            feed_contact_email=item.feed_contact_email,
            source_info=SourceInfo(producer_url=item.producer_url,
                                   authentication_type=item.authentication_type,
                                   authentication_info_url=item.authentication_info_url,
                                   api_key_parameter_name=item.api_key_parameter_name,
                                   license_url=item.license_url),
            redirects=item.redirect_ids,
            locations=item.locations,
            latest_dataset=LatestDataset(id=item.latest_dataset_id,
                                         hosted_url=item.latest_dataset_hosted_url,
                                         downloaded_at=item.latest_dataset_downloaded_at,
                                         hash=item.latest_dataset_hash)
        )
        assert result == expected

    def test_from_orm_gtfs_rt(self):
        item = copy.deepcopy(search_item)
        item.data_type = 'gtfs_rt'
        result = SearchFeeds200ResponseResultsInnerImpl.from_orm_gtfs_rt(item)
        assert result.data_type == 'gtfs_rt'
        expected = SearchFeeds200ResponseResultsInnerImpl(
            id=item.feed_stable_id,
            data_type=item.data_type,
            status=item.status,
            external_ids=item.external_ids,
            provider=item.provider,
            feed_name=item.feed_name,
            note=item.note,
            feed_contact_email=item.feed_contact_email,
            source_info=SourceInfo(producer_url=item.producer_url,
                                   authentication_type=item.authentication_type,
                                   authentication_info_url=item.authentication_info_url,
                                   api_key_parameter_name=item.api_key_parameter_name,
                                   license_url=item.license_url),
            redirects=item.redirect_ids,
            locations=item.locations,
            entity_types=item.entities,
            feed_references=item.feed_reference_ids,
        )
        assert result == expected

    def test_from_orm(self):
        item = copy.deepcopy(search_item)
        item.data_type = 'gtfs'
        result = SearchFeeds200ResponseResultsInnerImpl.from_orm(item)
        assert result.data_type == 'gtfs'

        item = copy.deepcopy(search_item)
        item.data_type = 'gtfs_rt'
        result = SearchFeeds200ResponseResultsInnerImpl.from_orm(item)
        assert result.data_type == 'gtfs_rt'

        assert SearchFeeds200ResponseResultsInnerImpl.from_orm(None) is None

        with pytest.raises(ValueError):
            item = copy.deepcopy(search_item)
            item.data_type = 'unknown'
            SearchFeeds200ResponseResultsInnerImpl.from_orm(item)
