import unittest

from geoalchemy2 import WKTElement

from shared.db_models.bounding_box_impl import BoundingBoxImpl
from feeds_gen.models.bounding_box import BoundingBox

POLYGON = "POLYGON ((3.0 1.0, 4.0 1.0, 4.0 2.0, 3.0 2.0, 3.0 1.0))"


class TestBoundingBoxImpl(unittest.TestCase):
    def test_from_orm(self):
        result: BoundingBox = BoundingBoxImpl.from_orm(WKTElement(POLYGON, srid=4326))
        assert result.minimum_latitude == 1.0
        assert result.maximum_latitude == 2.0
        assert result.minimum_longitude == 3.0
        assert result.maximum_longitude == 4.0

        assert BoundingBoxImpl.from_orm(None) is None
