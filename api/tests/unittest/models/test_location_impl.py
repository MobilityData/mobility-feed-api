import unittest

from feeds.impl.models.location_impl import LocationImpl
from database_gen.sqlacodegen_models import Location as LocationOrm
from feeds_gen.models.location import Location


class TestLocationImpl(unittest.TestCase):
    def test_from_orm(self):
        result = LocationImpl.from_orm(
            LocationOrm(country_code="US", subdivision_name="California", municipality="Los Angeles")
        )
        assert result == Location(country_code="US", subdivision_name="California", municipality="Los Angeles")

        assert LocationImpl.from_orm(None) is None
