import logging
import unittest
from unittest.mock import MagicMock

import pytest
from faker import Faker
from geoalchemy2 import WKTElement

from location_group_utils import GeopolygonAggregate
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Geopolygon,
    Osmlocationgroup,
    Gtfsfeed,
    Location,
)
from test_shared.test_utils.database_utils import default_db_url, clean_testing_db

faker = Faker()
logger = logging.getLogger(__name__)


class TestLocationGroupUtils(unittest.TestCase):
    def test_generate_color(self):
        from location_group_utils import generate_color

        # Darkest color generated
        self.assertEqual(generate_color(1, 1), "rgba(127, 0, 0, 1.0)")

    def test_geopolygon_object(self):
        from location_group_utils import GeopolygonObject

        geopolygon_orm = Geopolygon(
            osm_id=1,
            admin_level=2,
            name="Canada",
            iso_3166_1_code="CA",
            geometry=WKTElement("POINT(-73.5673 45.5017)", srid=4326),
        )
        geopolygon_object = GeopolygonObject(geopolygon_orm)
        self.assertEqual(str(geopolygon_object), "Canada [1 - Admin Level: 2]")

    def test_detach_from_session(self):
        from location_group_utils import detach_from_session, GeopolygonObject

        geopolygon_orm = Geopolygon(
            osm_id=1,
            admin_level=2,
            name="Canada",
            iso_3166_1_code="CA",
            geometry=WKTElement("POINT(-73.5673 45.5017)", srid=4326),
        )
        geopolygon_objects = detach_from_session([geopolygon_orm])
        self.assertIsInstance(geopolygon_objects[0], GeopolygonObject)

    def test_geopolygon_aggregate(self):
        geopolygons = [
            Geopolygon(
                osm_id=1,
                admin_level=2,
                name="Canada",
                iso_3166_1_code="CA",
                geometry=WKTElement("POINT(-73.5673 45.5017)", srid=4326),
            ),
            Geopolygon(
                osm_id=2,
                admin_level=3,
                name="Ontario",
                iso_3166_2_code="ON",
                geometry=WKTElement("POINT(-73.5673 45.5017)", srid=4326),
            ),
        ]
        location_group = Osmlocationgroup(
            group_id="1.1.1", group_name="Canada, Ontario", osms=geopolygons
        )
        from location_group_utils import GeopolygonAggregate

        geopolygon_aggregate = GeopolygonAggregate(location_group, 1)
        self.assertEqual(geopolygon_aggregate.country(), "Canada")
        self.assertEqual(geopolygon_aggregate.subdivision_name(), "Ontario")
        self.assertEqual(geopolygon_aggregate.municipality(), "Ontario")
        self.assertEqual(geopolygon_aggregate.location_id(), "CA-Ontario-Ontario")
        self.assertEqual(str(geopolygon_aggregate), "1.1.1 - Canada, Ontario")
        self.assertEqual(geopolygon_aggregate.display_name(), "🇨🇦 Canada, Ontario")
        geopolygon_aggregate_2 = GeopolygonAggregate(location_group, 1)
        geopolygon_aggregate.merge(geopolygon_aggregate_2)
        self.assertEqual(geopolygon_aggregate.stop_count, 2)

    @with_db_session(db_url=default_db_url)
    def test_extract_location_group(self, db_session):
        from location_group_utils import extract_location_aggregate

        clean_testing_db()
        geopolygon_country_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.country(),
            admin_level=2,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        geopolygon_subdivision_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_2_code=faker.country_code(),
        )
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        db_session.add(geopolygon_country_lvl)
        db_session.add(geopolygon_subdivision_lvl)
        db_session.add(feed)
        db_session.commit()
        stop_wkt = WKTElement("POINT (0.5 0.5)", srid=4326)
        aggregate = extract_location_aggregate(stop_wkt, logger, db_session)
        self.assertTrue(
            aggregate.iso_3166_1_code == geopolygon_country_lvl.iso_3166_1_code
        )
        self.assertTrue(
            aggregate.iso_3166_2_code == geopolygon_subdivision_lvl.iso_3166_2_code
        )

    @with_db_session(db_url=default_db_url)
    def test_extract_location_duplicate_admin_level(self, db_session):
        from location_group_utils import extract_location_aggregate

        print("test extract location duplicate admin level")
        clean_testing_db()
        print("Done cleaning the db")
        geopolygon_country_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.country(),
            admin_level=2,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        geopolygon_subdivision_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=2,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_2_code=faker.country_code(),
        )
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        db_session.add(geopolygon_country_lvl)
        db_session.add(geopolygon_subdivision_lvl)
        db_session.add(feed)
        db_session.commit()
        stop_wkt = WKTElement("POINT (0.5 0.5)", srid=4326)
        aggregate = extract_location_aggregate(stop_wkt, logger, db_session)
        self.assertIsNone(aggregate)

    @with_db_session(db_url=default_db_url)
    def test_extract_location_not_enough_geopolygons(self, db_session):
        from location_group_utils import extract_location_aggregate

        clean_testing_db()
        geopolygon_country_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.country(),
            admin_level=2,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        db_session.add(geopolygon_country_lvl)
        db_session.add(feed)
        db_session.commit()
        stop_wkt = WKTElement("POINT (0.5 0.5)", srid=4326)
        aggregate = extract_location_aggregate(stop_wkt, logger, db_session)
        self.assertIsNone(aggregate)

    @with_db_session(db_url=default_db_url)
    def test_extract_location_missing_iso_codes(self, db_session):
        from location_group_utils import extract_location_aggregate

        clean_testing_db()
        geopolygon_country_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.country(),
            admin_level=2,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        geopolygon_subdivision_lvl = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
        )
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        db_session.add(geopolygon_country_lvl)
        db_session.add(geopolygon_subdivision_lvl)
        db_session.add(feed)
        db_session.commit()
        stop_wkt = WKTElement("POINT (0.5 0.5)", srid=4326)
        aggregate = extract_location_aggregate(stop_wkt, logger, db_session)
        self.assertIsNone(aggregate)

    @with_db_session(db_url=default_db_url)
    def test_create_feed_osm_location(self, db_session):
        from location_group_utils import get_or_create_feed_osm_location_group

        clean_testing_db()
        feed_id = faker.uuid4(cast_to=str)
        feed = Gtfsfeed(id=feed_id, stable_id=faker.uuid4(cast_to=str))
        db_session.add(feed)
        db_session.commit()
        stops_count = faker.random_int()
        aggregate = GeopolygonAggregate(
            Osmlocationgroup(
                group_id=faker.uuid4(cast_to=str),
                group_name=faker.country(),
                osms=[
                    Geopolygon(
                        osm_id=faker.random_int(),
                        admin_level=2,
                        geometry=WKTElement(
                            "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326
                        ),
                        iso_3166_1_code=faker.country_code(),
                    )
                ],
            ),
            stops_count=stops_count,
        )
        feed_osm_location = get_or_create_feed_osm_location_group(
            feed_id, aggregate, db_session
        )
        self.assertIsNotNone(feed_osm_location)
        self.assertEqual(feed_osm_location.stops_count, stops_count)

    @with_db_session(db_url=default_db_url)
    def test_create_new_location(self, db_session):
        from reverse_geolocation_processor import get_or_create_location

        # Clean DB before test
        clean_testing_db()

        # Create sample Geopolygon and GeopolygonAggregate
        geopolygon_country = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        geopolygon_subdivision = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_2_code=faker.country_code(),
        )

        group = Osmlocationgroup(
            group_id=faker.uuid4(cast_to=str),
            group_name=f"{geopolygon_country.name}, {geopolygon_subdivision.name}",
            osms=[geopolygon_country, geopolygon_subdivision],
        )

        location_aggregate = GeopolygonAggregate(group, stops_count=5)

        # Call the function
        location = get_or_create_location(location_aggregate, logger, db_session)

        # Assert location is created
        self.assertIsNotNone(location)
        self.assertEqual(location.id, location_aggregate.location_id())
        self.assertEqual(location.country_code, location_aggregate.iso_3166_1_code)
        self.assertEqual(location.country, location_aggregate.country())
        self.assertEqual(
            location.subdivision_name, location_aggregate.subdivision_name()
        )
        self.assertEqual(location.municipality, location_aggregate.municipality())

    @with_db_session(db_url=default_db_url)
    def test_retrieve_existing_location(self, db_session):
        from reverse_geolocation_processor import get_or_create_location

        # Clean DB before test
        clean_testing_db()

        # Create sample Location
        existing_location = Location(
            id=faker.uuid4(cast_to=str),
            country_code=faker.country_code(),
            country=faker.country(),
            subdivision_name=faker.state(),
            municipality=faker.city(),
        )

        db_session.add(existing_location)
        db_session.commit()

        # Create GeopolygonAggregate with same location_id
        geopolygon_country = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_1_code=faker.country_code(),
        )
        geopolygon_subdivision = Geopolygon(
            osm_id=faker.random_int(),
            name=faker.city(),
            admin_level=3,
            geometry=WKTElement("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))", srid=4326),
            iso_3166_2_code=faker.country_code(),
        )

        group = Osmlocationgroup(
            group_id=faker.uuid4(cast_to=str),
            group_name=f"{geopolygon_country.name}, {geopolygon_subdivision.name}",
            osms=[geopolygon_country, geopolygon_subdivision],
        )

        location_aggregate = GeopolygonAggregate(group, stops_count=5)
        location_aggregate.location_id = (
            lambda: existing_location.id
        )  # Mocking location_id method

        # Call the function
        location = get_or_create_location(location_aggregate, logger, db_session)

        # Assert the existing location was returned
        self.assertIsNotNone(location)
        self.assertEqual(location.id, existing_location.id)
        self.assertEqual(location.country, existing_location.country)

    def test_retrieve_location_exception(self):
        from reverse_geolocation_processor import get_or_create_location

        mock_session = MagicMock()
        mock_session.query.side_effect = Exception("Test exception")
        location = get_or_create_location(None, logger, mock_session)
        self.assertIsNone(location)


@pytest.mark.parametrize(
    "values",
    [{"value": "CA", "expected": "Canada"}, {"value": "Canada", "expected": None}],
)
def test_location_country(values):
    """
    Test the country function with cases with valid and invalid ISO 3166_1 code
    """
    geopolygon = Geopolygon(
        osm_id=1,
        admin_level=2,
        name=values.get("value"),
        iso_3166_1_code=values.get("value"),
        geometry=WKTElement("POINT(-73.5673 45.5017)", srid=4326),
    )
    location_group = Osmlocationgroup(
        group_id="1.1.1", group_name="Canada, Ontario", osms=[geopolygon]
    )
    geopolygon_aggregate = GeopolygonAggregate(location_group, 1)

    assert geopolygon_aggregate.country() == values.get("expected")
