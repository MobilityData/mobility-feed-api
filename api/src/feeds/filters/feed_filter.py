from typing import Optional

from fastapi_filter.contrib.sqlalchemy import Filter

from database_gen.sqlacodegen_models import Feed


class FeedFilter(Filter):
    status: Optional[str]
    stable_id: Optional[str]
    provider__ilike: Optional[str]  # case insensitive
    data_type: Optional[str]

    class Constants(Filter.Constants):
        model = Feed
