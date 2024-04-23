from feeds_gen.models.location import Location
from database_gen.sqlacodegen_models import Location as LocationOrm


class LocationImpl(Location):
    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True
        orm_mode = True

    @classmethod
    def from_orm(cls, location: LocationOrm | None) -> Location | None:
        """Create a model instance from a SQLAlchemy a Location row object."""
        if not location:
            return None
        return cls(
            country_code=location.country_code,
            subdivision_name=location.subdivision_name,
            municipality=location.municipality,
        )
