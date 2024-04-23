from typing import Optional, List

from fastapi_filter.contrib.sqlalchemy import Filter

from database_gen.sqlacodegen_models import Gtfsrealtimefeed, Entitytype
from feeds.filters.gtfs_feed_filter import LocationFilter


class EntityTypeFilter(Filter):
    name__in: Optional[List[str]]

    class Constants(Filter.Constants):
        model = Entitytype


class GtfsRtFeedFilter(Filter):
    stable_id: Optional[str]
    provider__ilike: Optional[str]  # case insensitive
    producer_url__ilike: Optional[str]  # case insensitive
    entity_types: Optional[EntityTypeFilter]
    location: Optional[LocationFilter]

    class Constants(Filter.Constants):
        model = Gtfsrealtimefeed
