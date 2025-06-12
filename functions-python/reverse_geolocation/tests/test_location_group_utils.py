import unittest

import pytest
from faker import Faker
from geoalchemy2 import WKTElement

from location_group_utils import GeopolygonAggregate
from shared.database_gen.sqlacodegen_models import Geopolygon, Osmlocationgroup

faker = Faker()


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
