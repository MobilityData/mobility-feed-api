import unittest
from datetime import datetime
from zoneinfo import ZoneInfo 

from geoalchemy2 import WKTElement

from shared.database_gen.sqlacodegen_models import Gtfsdataset, Feed, Validationreport, Notice
from feeds.impl.models.bounding_box_impl import BoundingBoxImpl
from feeds.impl.models.latest_dataset_impl import LatestDatasetImpl

POLYGON = "POLYGON ((3.0 1.0, 4.0 1.0, 4.0 2.0, 3.0 2.0, 3.0 1.0))"


class TestLatestDatasetImpl(unittest.TestCase):
    def test_from_orm(self):
        now = datetime.now()
        assert LatestDatasetImpl.from_orm(
            Gtfsdataset(
                id="10",
                stable_id="stable_id",
                feed=Feed(stable_id="feed_stable_id"),
                hosted_url="http://example.com",
                note="note",
                downloaded_at=now,
                hash="hash",
                bounding_box=WKTElement(POLYGON, srid=4326),
                service_date_range_start=datetime(2024, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("Canada/Atlantic")),
                service_date_range_end=datetime(2025, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("Canada/Atlantic")),
                agency_timezone="Canada/Atlantic",
                validation_reports=[
                    Validationreport(validator_version="1.0.0"),
                    Validationreport(
                        validator_version="1.2.0",
                        notices=[
                            Notice(severity="INFO", total_notices=1),
                            Notice(severity="ERROR", total_notices=2, notice_code="foreign_key_violation"),
                            Notice(severity="ERROR", total_notices=1, notice_code="empty_column_name"),
                            Notice(severity="WARNING", total_notices=3),
                        ],
                    ),
                    Validationreport(validator_version="1.1.1"),
                ],
            )
        ) == LatestDatasetImpl(
            id="stable_id",
            feed_id="feed_stable_id",
            hosted_url="http://example.com",
            note="note",
            downloaded_at=now,
            hash="hash",
            bounding_box=BoundingBoxImpl(
                minimum_latitude=1.0,
                maximum_latitude=2.0,
                minimum_longitude=3.0,
                maximum_longitude=4.0,
            ),
            service_date_range_start=datetime(2024, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("Canada/Atlantic")),
            service_date_range_end=datetime(2025, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("Canada/Atlantic")),
            agency_timezone="Canada/Atlantic",
            validation_report={
                "validator_version": "1.2.0",
                "total_error": 3,
                "total_info": 1,
                "total_warning": 3,
                "unique_error_count": 2,
                "unique_info_count": 1,
                "unique_warning_count": 1,
            },
        )

        assert LatestDatasetImpl.from_orm(None) is None
