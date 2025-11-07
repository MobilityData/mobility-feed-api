from sqlalchemy.orm import Session

from feeds_gen.models.location import Location
import pycountry

from shared.common.locations_utils import create_or_get_location
from shared.database.database import with_db_session
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

    @classmethod
    @with_db_session
    def to_orm_from_dict(self, location_dict: dict, db_session: Session) -> LocationOrm | None:
        """Convert the Pydantic model instance to a SQLAlchemy Location row object."""
        return create_or_get_location(
            session=db_session,
            country=location_dict["country"],
            state_province=location_dict["subdivision_name"],
            city_name=location_dict["municipality"],
            country_code=location_dict["country_code"],
        )
