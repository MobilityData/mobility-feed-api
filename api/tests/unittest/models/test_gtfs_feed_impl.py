import copy
import unittest
from datetime import datetime, date

from geoalchemy2 import WKTElement

from database_gen.sqlacodegen_models import (
    Redirectingid,
    Feature,
    Validationreport,
    Gtfsdataset,
    Externalid,
    Location,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Entitytype,
    Notice,
    Feed,
)
from feeds.impl.models.bounding_box_impl import BoundingBoxImpl
from feeds.impl.models.external_id_impl import ExternalIdImpl
from feeds.impl.models.gtfs_feed_impl import GtfsFeedImpl
from feeds.impl.models.latest_dataset_impl import LatestDatasetImpl
from feeds.impl.models.location_impl import LocationImpl
from feeds.impl.models.redirect_impl import RedirectImpl
from feeds_gen.models.latest_dataset_validation_report import LatestDatasetValidationReport
from feeds_gen.models.source_info import SourceInfo

POLYGON = "POLYGON ((3.0 1.0, 4.0 1.0, 4.0 2.0, 3.0 2.0, 3.0 1.0))"

targetFeed = Feed(
    id="id1",
    stable_id="target_id",
    locations=[],
    externalids=[],
    gtfsdatasets=[],
    redirectingids=[],
)


def create_test_notice(notice_code: str, total_notices: int, severity: str):
    return Notice(
        dataset_id="dataset_id",
        validation_report_id="validation_report_id",
        notice_code=notice_code,
        total_notices=total_notices,
        severity=severity,
    )


gtfs_feed_orm = Gtfsfeed(
    id="id",
    data_type="gtfs",
    feed_name="feed_name",
    note="note",
    producer_url="producer_url",
    authentication_type=1,
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
            stable_id="dataset_stable_id",
            feed_id="feed_id",
            hosted_url="hosted_url",
            note="note",
            downloaded_at=datetime(year=2022, month=12, day=31, hour=13, minute=45, second=56),
            hash="hash",
            service_date_range_start= date(2024, 1, 1),
            service_date_range_end= date(2025, 1, 1),
            bounding_box=WKTElement(POLYGON, srid=4326),
            latest=True,
            validation_reports=[
                Validationreport(
                    id="id",
                    validator_version="validator_version",
                    validated_at=datetime(year=2022, month=12, day=31, hour=13, minute=45, second=56),
                    html_report="html_report",
                    json_report="json_report",
                    features=[Feature(name="feature")],
                    notices=[
                        create_test_notice("notice_code1", 1, "INFO"),
                        create_test_notice("notice_code2", 3, "INFO"),
                        create_test_notice("notice_code3", 7, "ERROR"),
                        create_test_notice("notice_code4", 9, "ERROR"),
                        create_test_notice("notice_code5", 11, "ERROR"),
                        create_test_notice("notice_code6", 13, "WARNING"),
                        create_test_notice("notice_code7", 15, "WARNING"),
                        create_test_notice("notice_code8", 17, "WARNING"),
                        create_test_notice("notice_code9", 19, "WARNING"),
                    ],
                )
            ],
        )
    ],
    redirectingids=[
        Redirectingid(source_id="source_id", target_id="id1", redirect_comment="redirect_comment", target=targetFeed)
    ],
    gtfs_rt_feeds=[
        Gtfsrealtimefeed(
            id="id",
            entitytypes=[Entitytype(name="entitytype")],
        )
    ],
)

expected_gtfs_feed_result = GtfsFeedImpl(
    id="stable_id",
    data_type="gtfs",
    status="active",
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
    locations=[
        LocationImpl(
            country_code="CA",
            country="Canada",
            subdivision_name="subdivision_name",
            municipality="municipality",
        )
    ],
    latest_dataset=LatestDatasetImpl(
        id="dataset_stable_id",
        hosted_url="hosted_url",
        bounding_box=BoundingBoxImpl(
            minimum_latitude=1.0, maximum_latitude=2.0, minimum_longitude=3.0, maximum_longitude=4.0
        ),
        downloaded_at=datetime(year=2022, month=12, day=31, hour=13, minute=45, second=56),
        hash="hash",
        validation_report=LatestDatasetValidationReport(
            total_error=27,
            total_warning=64,
            total_info=4,
            unique_error_count=3,
            unique_warning_count=4,
            unique_info_count=2,
        ),
        service_date_range_start= "2024-01-01",
        service_date_range_end="2025-01-01"
    ),
)


class TestGtfsFeedImpl(unittest.TestCase):
    """Test the `GtfsFeedImpl` model."""

    def test_from_orm_all_fields(self):
        """Test the `from_orm` method with all fields."""
        result = GtfsFeedImpl.from_orm(gtfs_feed_orm, {})
        assert result == expected_gtfs_feed_result

    def test_from_orm_empty_fields(self):
        """Test the `from_orm` method with not provided fields."""
        # Test with empty fields and None values
        # No error should be raised
        # Target is set to None as deep copy is failing for unknown reasons
        # At the end of the test, the target is set back to the original value
        gtfs_feed_orm.redirectingids[0].target = None
        target_feed_orm = copy.deepcopy(gtfs_feed_orm)
        target_feed_orm.feed_name = ""
        target_feed_orm.provider = None
        target_feed_orm.externalids = []
        target_feed_orm.redirectingids = []

        target_expected_gtfs_feed_result = copy.deepcopy(expected_gtfs_feed_result)
        target_expected_gtfs_feed_result.feed_name = ""
        target_expected_gtfs_feed_result.provider = None
        target_expected_gtfs_feed_result.external_ids = []
        target_expected_gtfs_feed_result.redirects = []

        result = GtfsFeedImpl.from_orm(target_feed_orm)
        assert result == target_expected_gtfs_feed_result
        # Set the target back to the original value
        gtfs_feed_orm.redirectingids[0].target = targetFeed
