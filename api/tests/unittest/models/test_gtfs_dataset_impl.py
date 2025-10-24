import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from geoalchemy2 import WKTElement

from shared.database_gen.sqlacodegen_models import Validationreport, Gtfsdataset, Feed
from shared.db_models.gtfs_dataset_impl import GtfsDatasetImpl

POLYGON = "POLYGON ((3.0 1.0, 4.0 1.0, 4.0 2.0, 3.0 2.0, 3.0 1.0))"


class TestGtfsDatasetImpl(unittest.TestCase):
    def test_from_orm_latest_validation_report(self):
        result = GtfsDatasetImpl.from_orm_latest_validation_report(
            [
                Validationreport(validator_version="1.0.0"),
                Validationreport(validator_version="0.2.0"),
                Validationreport(validator_version="1.1.1"),
            ]
        )
        assert result.validator_version == "1.1.1"

        result = GtfsDatasetImpl.from_orm_latest_validation_report([])
        assert result is None

        result = GtfsDatasetImpl.from_orm_latest_validation_report(None)
        assert result is None

    def test_from_orm(self):
        now = datetime.now()
        orm = Gtfsdataset(
            id="10",
            stable_id="stable_id",
            feed=Feed(stable_id="feed_stable_id"),
            hosted_url="http://example.com",
            note="note",
            downloaded_at=now,
            hash="hash",
            bounding_box=WKTElement(POLYGON, srid=4326),
            validation_reports=[
                Validationreport(validator_version="1.0.0"),
                Validationreport(validator_version="0.2.0"),
                Validationreport(validator_version="1.1.1"),
            ],
            service_date_range_start=datetime(2024, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("Canada/Atlantic")),
            service_date_range_end=datetime(2025, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("Canada/Atlantic")),
            agency_timezone="Canada/Atlantic",
        )
        result = GtfsDatasetImpl.from_orm(orm)
        assert result.id == "stable_id"
        assert result.feed_id == "feed_stable_id"
        assert result.hosted_url == "http://example.com"
        assert result.note == "note"
        assert result.hash == "hash"
        assert result.downloaded_at == now
        assert result.bounding_box is not None
        assert result.bounding_box.minimum_latitude == 1.0
        assert result.bounding_box.maximum_latitude == 2.0
        assert result.bounding_box.minimum_longitude == 3.0
        assert result.bounding_box.maximum_longitude == 4.0
        assert result.validation_report.validator_version == "1.1.1"
        assert result.service_date_range_start == datetime(2024, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("Canada/Atlantic"))
        assert result.service_date_range_end == datetime(2025, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("Canada/Atlantic"))
        assert result.agency_timezone == "Canada/Atlantic"

        assert GtfsDatasetImpl.from_orm(None) is None
