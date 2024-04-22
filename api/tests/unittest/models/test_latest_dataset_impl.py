import unittest
from datetime import datetime

from geoalchemy2 import WKTElement

from database_gen.sqlacodegen_models import Gtfsdataset, Feed, Validationreport, Notice
from feeds.impl.models.latest_dateset_impl import LatestDatasetImpl
from feeds_gen.models.latest_dataset import LatestDataset

POLYGON = "POLYGON ((3.0 1.0, 4.0 1.0, 4.0 2.0, 3.0 2.0, 3.0 1.0))"


class TestLatestDatasetImpl(unittest.TestCase):

    def test_from_orm(self):
        now = datetime.now()
        assert LatestDatasetImpl.from_orm(Gtfsdataset(
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
                Validationreport(validator_version="1.2.0",
                                 notices=[
                                     Notice(severity="INFO", total_notices=1),
                                     Notice(severity="ERROR", total_notices=2),
                                     Notice(severity="WARNING", total_notices=3)
                                 ]),
                Validationreport(validator_version="1.1.1"),
            ],
        )) == LatestDataset(
            id="stable_id",
            feed_id="feed_stable_id",
            hosted_url="http://example.com",
            note="note",
            downloaded_at=now,
            hash="hash",
            bounding_box={
                "minimum_latitude": 1.0,
                "maximum_latitude": 2.0,
                "minimum_longitude": 3.0,
                "maximum_longitude": 4.0
            },
            validation_report={
                "validator_version": "1.2.0",
                "total_error": 2,
                "total_info": 1,
                "total_warning": 3
            }
        )

        assert LatestDatasetImpl.from_orm(None) is None
