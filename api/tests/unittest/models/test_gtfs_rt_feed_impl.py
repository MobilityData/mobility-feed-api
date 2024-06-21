import unittest
import copy

from database_gen.sqlacodegen_models import Gtfsrealtimefeed, Entitytype, Externalid, Location, Redirectingid
from feeds_gen.models.source_info import SourceInfo
from feeds.impl.models.gtfs_rt_feed_impl import GtfsRTFeedImpl
from feeds.impl.models.external_id_impl import ExternalIdImpl
from feeds.impl.models.location_impl import LocationImpl
from feeds.impl.models.redirect_impl import RedirectImpl
from feeds.impl.models.entity_type_impl import EntitytypeImpl


gtfs_rt_feed_orm = Gtfsrealtimefeed(
    stable_id="id",
    data_type="data_type",
    status="status",
    externalids=[
        Externalid(
            associated_id="associated_id",
            source="source",
        )
    ],
    provider="provider",
    feed_name="feed_name",
    note="note",
    feed_contact_email="feed_contact_email",
    producer_url="producer_url",
    authentication_type=1,
    authentication_info_url="authentication_info_url",
    api_key_parameter_name="api_key_parameter_name",
    license_url="license_url",
    redirectingids=[
        Redirectingid(
            target_id="target_id",
            redirect_comment="redirect_comment",
        )
    ],
    entitytypes=[Entitytype(name="entitytype")],
    locations=[
        Location(
            id="id",
            country_code="country_code",
            subdivision_name="subdivision_name",
            municipality="municipality",
        )
    ],
)

expected_gtfs_rt_feed_result = GtfsRTFeedImpl(
    id="id",
    data_type="data_type",
    status="status",
    external_ids=[ExternalIdImpl(external_id="associated_id", source="source")],
    provider="provider",
    feed_name="feed_name",
    note="note",
    feed_contact_email="feed_contact_email",
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
    entity_types=[EntitytypeImpl(name="name")],
    locations=[
        LocationImpl(
            country_code="country_code",
            subdivision_name="subdivision_name",
            municipality="municipality",
        )
    ],
)


class TestGtfsRTFeedImpl(unittest.TestCase):
    def test_from_orm_all_fields(self):
        result = GtfsRTFeedImpl.from_orm(gtfs_rt_feed_orm)
        assert result == expected_gtfs_rt_feed_result

    def test_from_orm_empty_fields(self):
        """Test the `from_orm` method with not provided fields."""
        # Test with empty fields and None values
        # No error should be raised
        target_feed_orm = copy.deepcopy(gtfs_rt_feed_orm)
        target_feed_orm.feed_name = ""
        target_feed_orm.provider = None
        target_feed_orm.externalids = []
        target_feed_orm.redirectingids = []

        target_expected_gtfs_rt_feed_result = copy.deepcopy(expected_gtfs_rt_feed_result)
        target_expected_gtfs_rt_feed_result.feed_name = ""
        target_expected_gtfs_rt_feed_result.provider = None
        target_expected_gtfs_rt_feed_result.external_ids = []
        target_expected_gtfs_rt_feed_result.redirects = []

        result = GtfsRTFeedImpl.from_orm(target_feed_orm)
        assert result == target_expected_gtfs_rt_feed_result
