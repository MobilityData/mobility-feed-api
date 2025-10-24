import unittest

from shared.db_models.location_impl import LocationImpl
from shared.database_gen.sqlacodegen_models import Location as LocationOrm


class TestLocationImpl(unittest.TestCase):
    def test_from_orm(self):
        result = LocationImpl.from_orm(
            LocationOrm(
                country_code="US", subdivision_name="California", municipality="Los Angeles", country="United States"
            )
        )
        assert result == LocationImpl(
            country_code="US", country="United States", subdivision_name="California", municipality="Los Angeles"
        )

        assert LocationImpl.from_orm(None) is None
