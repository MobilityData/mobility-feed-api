from typing import Optional, List

from fastapi_filter.contrib.sqlalchemy import Filter

from database_gen.sqlacodegen_models import Gtfsrealtimefeed, Entitytype
from feeds.filters.gtfs_feed_filter import LocationFilter
from utils.param_utils import normalize_str_parameter


class EntityTypeFilter(Filter):
    name__in: Optional[List[str]]

    class Constants(Filter.Constants):
        model = Entitytype

    def __init__(self, *args, **kwargs):
        kwargs_normalized = normalize_str_parameter("name__in", **kwargs)
        super().__init__(*args, **kwargs_normalized)


class GtfsRtFeedFilter(Filter):
    stable_id: Optional[str]
    provider__ilike: Optional[str]  # case insensitive
    producer_url__ilike: Optional[str]  # case insensitive
    entity_types: Optional[EntityTypeFilter]
    location: Optional[LocationFilter]

    def __init__(self, *args, **kwargs):
        kwargs_normalized = normalize_str_parameter("stable_id", **kwargs)
        kwargs_normalized = normalize_str_parameter("provider__ilike", **kwargs_normalized)
        kwargs_normalized = normalize_str_parameter("producer_url__ilike", **kwargs_normalized)
        super().__init__(*args, **kwargs_normalized)

    class Constants(Filter.Constants):
        model = Gtfsrealtimefeed
