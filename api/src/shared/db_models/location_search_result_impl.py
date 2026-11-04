from typing import Optional

from feeds_gen.models.location_feed_counts import LocationFeedCounts
from feeds_gen.models.location_search_result import LocationSearchResult

from shared.database_gen.sqlacodegen_models import t_geopolygonlocationsearch

LOCATION_TYPE_CONTINENT = "continent"


class LocationSearchResultImpl(LocationSearchResult):
    """Implementation of the `LocationSearchResult` model.
    This class converts a SQLAlchemy row from the geopolygon location search read model
    to a Pydantic model instance."""

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, location_row: t_geopolygonlocationsearch, feed_counts: Optional[LocationFeedCounts] = None):
        """Create a model instance from a SQLAlchemy row object.
        The row may carry the `continent_slug` and `continent_name` of its continent."""
        if location_row is None:
            return None
        return cls(
            location_id=location_row.osm_id,
            parent_location_id=location_row.parent_osm_id,
            name=location_row.name,
            alt_name=location_row.alt_name,
            location_type=location_row.location_type,
            continent_code=location_row.continent_code,
            continent_slug=getattr(location_row, "continent_slug", None),
            continent_name=getattr(location_row, "continent_name", None),
            slug=location_row.slug,
            path_slugs=location_row.path_slugs or [],
            feed_counts=feed_counts,
            country_name=location_row.country_name,
            country_code=location_row.country_code,
            subdivision_name=location_row.subdivision_name,
            subdivision_code=location_row.subdivision_code,
            path_names=location_row.path_names or [],
            display_name=location_row.display_name,
        )

    @classmethod
    def from_continent(cls, continent_row, feed_counts: Optional[LocationFeedCounts] = None):
        """Create a model instance from a row of the continent table (`code`, `slug` and `name`).
        Continents are not geopolygons: they have no location id, parent or ISO code."""
        if continent_row is None:
            return None
        return cls(
            location_id=None,
            parent_location_id=None,
            name=continent_row.name,
            alt_name=None,
            location_type=LOCATION_TYPE_CONTINENT,
            continent_code=continent_row.code,
            continent_slug=continent_row.slug,
            continent_name=continent_row.name,
            slug=continent_row.slug,
            path_slugs=[],
            feed_counts=feed_counts,
            country_name=None,
            country_code=None,
            subdivision_name=None,
            subdivision_code=None,
            path_names=[],
            display_name=continent_row.name,
        )
