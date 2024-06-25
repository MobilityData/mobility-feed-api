from geoalchemy2 import WKBElement
from geoalchemy2.shape import to_shape

from feeds_gen.models.bounding_box import BoundingBox


class BoundingBoxImpl(BoundingBox):
    """Implementation of the `BoundingBox` model.
    This class converts a SQLAlchemy geometry values to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, geometry_value: WKBElement | None) -> BoundingBox | None:
        """Create a model instance from a SQLAlchemy a WKBElement value."""
        if geometry_value is None or geometry_value.data is None:
            return None
        shape = to_shape(geometry_value)
        return BoundingBoxImpl(
            minimum_latitude=shape.bounds[1],
            maximum_latitude=shape.bounds[3],
            minimum_longitude=shape.bounds[0],
            maximum_longitude=shape.bounds[2],
        )
