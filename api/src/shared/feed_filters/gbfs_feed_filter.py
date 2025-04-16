from typing import Optional

from fastapi_filter.contrib.sqlalchemy import Filter

from shared.database_gen.sqlacodegen_models import Gbfsfeed, Gbfsversion
from shared.feed_filters.gtfs_feed_filter import LocationFilter


class GbfsVersionFilter(Filter):
    version: Optional[str]

    class Constants(Filter.Constants):
        model = Gbfsversion


class GbfsFeedFilter(Filter):
    stable_id: Optional[str] = None
    provider__ilike: Optional[str] = None  # case-insensitive
    producer_url__ilike: Optional[str] = None  # case-insensitive
    location: Optional[LocationFilter] = None
    system_id: Optional[str] = None
    version: Optional[GbfsVersionFilter] = None

    class Constants(Filter.Constants):
        model = Gbfsfeed
