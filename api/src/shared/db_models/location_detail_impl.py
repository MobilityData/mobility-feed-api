from typing import Optional

from feeds_gen.models.location_detail import LocationDetail
from feeds_gen.models.location_feed_counts import LocationFeedCounts
from feeds_gen.models.location_search_response import LocationSearchResponse

from shared.database_gen.sqlacodegen_models import t_geopolygonlocationsearch
from shared.db_models.location_search_result_impl import location_fields


class LocationDetailImpl(LocationDetail):
    """Implementation of the `LocationDetail` model: a location of the geopolygon location search read model, with
    the first page of its direct children when they are requested."""

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(
        cls,
        location_row: t_geopolygonlocationsearch,
        feed_counts: Optional[LocationFeedCounts] = None,
        children: Optional[LocationSearchResponse] = None,
    ):
        """Create a model instance from a SQLAlchemy row object."""
        if location_row is None:
            return None
        return cls(**location_fields(location_row, feed_counts), children=children)
