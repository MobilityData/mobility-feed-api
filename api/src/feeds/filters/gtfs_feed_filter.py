from typing import Optional

from fastapi_filter.contrib.sqlalchemy import Filter

from database_gen.sqlacodegen_models import Location, Gtfsfeed
from utils.param_utils import normalize_str_parameter


class LocationFilter(Filter):
    country_code: Optional[str]
    subdivision_name__ilike: Optional[str]
    municipality__ilike: Optional[str]

    def __init__(self, *args, **kwargs):
        kwargs_normalized = normalize_str_parameter("country_code", **kwargs)
        kwargs_normalized = normalize_str_parameter("subdivision_name__ilike", **kwargs_normalized)
        kwargs_normalized = normalize_str_parameter("municipality__ilike", **kwargs_normalized)
        super().__init__(*args, **kwargs_normalized)

    class Constants(Filter.Constants):
        model = Location


class GtfsFeedFilter(Filter):
    stable_id: Optional[str]
    provider__ilike: Optional[str]  # case insensitive
    producer_url__ilike: Optional[str]  # case insensitive
    location: Optional[LocationFilter]

    class Constants(Filter.Constants):
        model = Gtfsfeed
