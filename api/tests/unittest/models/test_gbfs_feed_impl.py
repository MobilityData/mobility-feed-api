import unittest
from datetime import datetime

from geoalchemy2 import WKTElement

from feeds_gen.models.source_info import SourceInfo
from shared.database_gen.sqlacodegen_models import Gbfsfeed, Location, Gbfsversion
from feeds.impl.models.gbfs_feed_impl import GbfsFeedImpl
from feeds.impl.models.location_impl import LocationImpl
from feeds.impl.models.gbfs_version_impl import GbfsVersionImpl
from feeds.impl.models.bounding_box_impl import BoundingBoxImpl

POLYGON = "POLYGON ((3.0 1.0, 4.0 1.0, 4.0 2.0, 3.0 2.0, 3.0 1.0))"


class TestGbfsFeedImpl(unittest.TestCase):
    def setUp(self):
        self.location_orm = Location(
            id="loc1",
            country_code="US",
            country="United States",
            subdivision_name="California",
            municipality="San Francisco",
        )
        self.version_orm = Gbfsversion(
            id="ver1",
            version="2.2",
            url="https://example.com/gbfs.json",
        )
        self.bounding_box_orm = WKTElement(POLYGON, srid=4326)
        self.feed_orm = Gbfsfeed(
            id="feed1",
            stable_id="feed_stable_1",
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            data_type="gbfs",
            system_id="sys1",
            operator_url="https://provider.com",
            locations=[self.location_orm],
            gbfsversions=[self.version_orm],
            bounding_box=self.bounding_box_orm,
            bounding_box_generated_at=datetime(2024, 1, 1, 12, 0, 0),
            authentication_type=0,
            authentication_info_url="https://auth.info",
            api_key_parameter_name="api_key",
            license_url="https://license.info",
        )

    def test_from_orm_all_fields(self):
        expected = GbfsFeedImpl(
            id="feed_stable_1",
            system_id="sys1",
            related_links=[],
            data_type="gbfs",
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            external_ids=[],
            redirects=[],
            provider_url="https://provider.com",
            locations=[LocationImpl.from_orm(self.location_orm)],
            versions=[GbfsVersionImpl.from_orm(self.version_orm)],
            bounding_box=BoundingBoxImpl.from_orm(self.bounding_box_orm),
            bounding_box_generated_at=datetime(2024, 1, 1, 12, 0, 0),
            source_info=SourceInfo(
                producer_url=None,
                authentication_type=0,
                authentication_info_url="https://auth.info",
                api_key_parameter_name="api_key",
                license_url="https://license.info",
            ),
        )
        result = GbfsFeedImpl.from_orm(self.feed_orm)
        self.assertEqual(result, expected)

    def test_from_orm_empty_fields(self):
        feed_orm = Gbfsfeed(
            id="feed2",
            stable_id="feed_stable_2",
            system_id=None,
            operator_url=None,
            locations=[],
            gbfsversions=[],
            bounding_box=None,
            bounding_box_generated_at=None,
        )
        expected = GbfsFeedImpl(
            id="feed_stable_2",
            system_id=None,
            provider_url=None,
            external_ids=[],
            redirects=[],
            locations=[],
            versions=[],
            related_links=[],
            bounding_box=None,
            bounding_box_generated_at=None,
            source_info=SourceInfo(
                producer_url=None,
                authentication_type=None,
                authentication_info_url=None,
                api_key_parameter_name=None,
                license_url=None,
            ),
        )
        result = GbfsFeedImpl.from_orm(feed_orm)
        self.assertEqual(result, expected)

    def test_from_orm_none(self):
        result = GbfsFeedImpl.from_orm(None)
        self.assertIsNone(result)
