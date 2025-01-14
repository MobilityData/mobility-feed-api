from typing import Optional

from fastapi_filter.contrib.sqlalchemy import Filter

from shared.database_gen.sqlacodegen_models import Feed
from utils.param_utils import normalize_str_parameter


class FeedFilter(Filter):
    status: Optional[str]
    stable_id: Optional[str]
    provider__ilike: Optional[str]  # case insensitive
    producer_url__ilike: Optional[str]  # case insensitive

    def __init__(self, *args, **kwargs):
        kwargs_normalized = normalize_str_parameter("status", **kwargs)
        kwargs_normalized = normalize_str_parameter("stable_id", **kwargs_normalized)
        kwargs_normalized = normalize_str_parameter("provider__ilike", **kwargs_normalized)
        kwargs_normalized = normalize_str_parameter("producer_url__ilike", **kwargs_normalized)
        super().__init__(*args, **kwargs_normalized)

    class Constants(Filter.Constants):
        model = Feed
