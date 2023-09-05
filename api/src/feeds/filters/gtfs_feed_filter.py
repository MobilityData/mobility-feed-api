from typing import Optional

from fastapi_filter.contrib.sqlalchemy import Filter

from database_gen.sqlacodegen_models import Location, Gtfsfeed


class LocationFilter(Filter):
    country_code: Optional[str]
    subdivision_name__ilike: Optional[str]
    municipality__ilike: Optional[str]

    class Constants(Filter.Constants):
        model = Location


class GtfsFeedFilter(Filter):
    stable_id: Optional[str]
    provider__ilike: Optional[str]  # case insensitive
    location: Optional[LocationFilter]

    class Constants(Filter.Constants):
        model = Gtfsfeed
