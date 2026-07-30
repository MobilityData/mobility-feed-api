from feeds_gen.models.location_search_result import LocationSearchResult

from shared.database_gen.sqlacodegen_models import t_geopolygonlocationsearch


class LocationSearchResultImpl(LocationSearchResult):
    """Implementation of the `LocationSearchResult` model.
    This class converts a SQLAlchemy row from the geopolygon location search read model
    to a Pydantic model instance."""

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, location_row: t_geopolygonlocationsearch):
        """Create a model instance from a SQLAlchemy row object."""
        if location_row is None:
            return None
        return cls(
            location_id=location_row.osm_id,
            parent_location_id=location_row.parent_osm_id,
            name=location_row.name,
            alt_name=location_row.alt_name,
            location_type=location_row.location_type,
            country_name=location_row.country_name,
            country_code=location_row.country_code,
            subdivision_name=location_row.subdivision_name,
            subdivision_code=location_row.subdivision_code,
            path_names=location_row.path_names or [],
            display_name=location_row.display_name,
        )
