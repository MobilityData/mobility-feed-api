from typing import Optional
from datetime import datetime
from fastapi_filter.contrib.sqlalchemy import Filter

from shared.database_gen.sqlacodegen_models import Gtfsdataset
from utils.param_utils import normalize_str_parameter


class GtfsDatasetFilter(Filter):
    downloaded_at__lte: Optional[datetime]
    downloaded_at__gte: Optional[datetime]

    def __init__(self, *args, **kwargs):
        kwargs_normalized = normalize_str_parameter("downloaded_at__lte", **kwargs)
        kwargs_normalized = normalize_str_parameter("downloaded_at__gte", **kwargs_normalized)
        super().__init__(*args, **kwargs_normalized)

    class Constants(Filter.Constants):
        model = Gtfsdataset
