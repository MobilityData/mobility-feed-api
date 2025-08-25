import logging
import unittest
from unittest.mock import patch
import pandas as pd
from geoalchemy2 import WKTElement
from shapely import wkt
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Geopolygon
from test_shared.test_utils.database_utils import clean_testing_db, default_db_url

logger = logging.getLogger(__name__)


class TestExtractLocationAggregatesPerPolygon(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    @patch("strategy_extraction_per_polygon.get_geopolygons_covers")
    def test_valid_stops_processing(self, mock_get_geopolygons_covers, db_session):
        from strategy_extraction_per_polygon import (
            extract_location_aggregates_per_polygon,
        )

        # Clean the database
        clean_testing_db()

        # Create a test feed
        feed = Gtfsfeed(id="test_feed", stable_id="test_feed", status="active")
        db_session.add(feed)
        db_session.commit()

        # Prepare stops DataFrame
        stops_df = pd.DataFrame(
            {
                "stop_id": [1, 2],
                "stop_lat": [2.0, 3.0],
                "stop_lon": [2.0, 3.0],
            }
        )
        stops_df["geometry"] = stops_df.apply(
            lambda x: WKTElement(f"POINT ({x['stop_lon']} {x['stop_lat']})", srid=4326),
            axis=1,
        )

        qc_geopolygons = [
            Geopolygon(
                osm_id=1,
                admin_level=2,
                geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
                iso_3166_1_code="CA",
                name="Canada",
            ),
            Geopolygon(
                osm_id=2,
                admin_level=4,
                geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
                iso_3166_2_code="CA-QC",
                name="Quebec",
            ),
        ]
        mtl_geopolygons = [
            Geopolygon(
                osm_id=3,
                admin_level=2,
                geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
                iso_3166_1_code="CA",
                name="Canada",
            ),
            Geopolygon(
                osm_id=4,
                admin_level=4,
                geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
                iso_3166_2_code="CA-QC",
                name="Quebec",
            ),
            Geopolygon(
                osm_id=5,
                admin_level=7,
                geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
                iso_3166_2_code="CA-QC",
                name="Montreal",
            ),
        ]

        def mock_geopolygons_covers(stop: WKTElement, *args, **kwargs):
            point = wkt.loads(stop.desc)
            # Extract latitude
            longitude = point.x
            if longitude == 2.0:
                return mtl_geopolygons
            else:
                return qc_geopolygons

        mock_get_geopolygons_covers.side_effect = mock_geopolygons_covers

        # Prepare location_aggregates dict
        location_aggregates = {}

        # Call the function
        extract_location_aggregates_per_polygon(
            feed=feed,
            stops_df=stops_df,
            location_aggregates=location_aggregates,
            use_cache=False,
            logger=logger,
            db_session=db_session,
        )

        # Assertions
        self.assertEqual(2, len(location_aggregates))
        self.assertTrue("3.4.5" in location_aggregates)
        self.assertTrue("1.2" in location_aggregates)
        location_aggregate = location_aggregates["1.2"]
        self.assertEqual("1.2", location_aggregate.group_id)
        self.assertEqual(1, location_aggregate.stop_count)
        self.assertEqual("CA", location_aggregate.iso_3166_1_code)

        clean_testing_db()
