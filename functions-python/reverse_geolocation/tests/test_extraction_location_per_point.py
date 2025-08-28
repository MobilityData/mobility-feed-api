import logging
import unittest
from unittest.mock import patch


import pandas as pd
from faker import Faker
from geoalchemy2 import WKTElement

from location_group_utils import GeopolygonAggregate
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsrealtimefeed,
    Geopolygon,
    Osmlocationgroup,
)
from test_shared.test_utils.database_utils import clean_testing_db, default_db_url


faker = Faker()
logger = logging.getLogger(__name__)


class TestReverseGeolocationProcessor(unittest.TestCase):
    @patch("location_group_utils.extract_location_aggregate")
    @with_db_session(db_url=default_db_url)
    def test_extract_location_aggregates_per_point(
        self,
        mock_extract_location_aggregate,
        db_session,
    ):
        from strategy_extraction_per_point import extract_location_aggregates_per_point

        clean_testing_db()

        # Create sample feed
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        gtfs_rt_feed = Gtfsrealtimefeed(
            id=faker.uuid4(cast_to=str), stable_id=faker.uuid4(cast_to=str)
        )
        feed.gtfs_rt_feeds = [gtfs_rt_feed]
        db_session.add(feed)
        db_session.commit()

        # Prepare stops DataFrame
        stops_df = pd.DataFrame(
            {
                "stop_id": [1, 2, 3],
                "stop_lat": [2.0, 3.0, 10.0],  # Two inside polygon, one unmatched
                "stop_lon": [2.0, 3.0, 10.0],
            }
        )

        stops_df["geometry"] = stops_df.apply(
            lambda x: WKTElement(f"POINT ({x['stop_lon']} {x['stop_lat']})", srid=4326),
            axis=1,
        )

        # Prepare mock GeopolygonAggregate for matched stops
        geopolygon = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 5 0, 5 5, 0 5, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )

        group = Osmlocationgroup(
            group_id=faker.uuid4(cast_to=str),
            group_name=geopolygon.name,
            osms=[geopolygon],
        )

        mock_aggregate = GeopolygonAggregate(group, stops_count=1)
        db_session.add(group)
        db_session.commit()

        # Mock extract_location_aggregate behavior
        def side_effect(stop_geometry, _, __):
            if stop_geometry.data == "POINT (10.0 10.0)":  # Simulate unmatched stop
                return None
            return mock_aggregate

        mock_extract_location_aggregate.side_effect = side_effect

        # Prepare location_aggregates dict (empty initially)
        location_aggregates = {}

        # Call the function
        extract_location_aggregates_per_point(
            feed=feed,
            stops_df=stops_df,
            location_aggregates=location_aggregates,
            use_cache=False,
            logger=logger,
            db_session=db_session,
        )

        # Assertions
        # Ensure only matched stops are aggregated
        self.assertEqual(len(location_aggregates), 1)
        first_aggregate = list(location_aggregates.values())[0]
        self.assertIsInstance(first_aggregate, GeopolygonAggregate)
        self.assertEqual(first_aggregate.stop_count, 2)  # Two matched stops

        db_session.close_all()
