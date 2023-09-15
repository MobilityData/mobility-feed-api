from typing import Optional, List

from fastapi_filter.contrib.sqlalchemy import Filter

from database_gen.sqlacodegen_models import Gtfsrealtimefeed, t_entitytypefeed, Entitytype


class EntityTypeFilter(Filter):
    name__in: Optional[List[str]]

    class Constants(Filter.Constants):
        model = Entitytype


class GtfsRtFeedFilter(Filter):
    stable_id: Optional[str]
    provider__ilike: Optional[str]  # case insensitive
    producer_url__ilike: Optional[str]  # case insensitive
    entity_types: Optional[EntityTypeFilter]

    class Constants(Filter.Constants):
        model = Gtfsrealtimefeed
