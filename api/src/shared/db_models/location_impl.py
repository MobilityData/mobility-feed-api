from feeds_gen.models.location import Location
import pycountry
from shared.database_gen.sqlacodegen_models import Location as LocationOrm


class LocationImpl(Location):
    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, location: LocationOrm | None) -> Location | None:
        """Create a model instance from a SQLAlchemy a Location row object."""
        if not location:
            return None
        country_name = location.country
        if not country_name:
            try:
                country_name = pycountry.countries.get(alpha_2=location.country_code).name
            except AttributeError:
                pass
        return cls(
            country_code=location.country_code,
            country=country_name,
            subdivision_name=location.subdivision_name,
            municipality=location.municipality,
        )
