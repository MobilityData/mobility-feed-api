from typing import Optional
from datetime import datetime
from fastapi_filter.contrib.sqlalchemy import Filter

from database_gen.sqlacodegen_models import Gtfsdataset


class GtfsDatasetFilter(Filter):
    downloaded_at__lte: Optional[datetime]
    downloaded_at__gte: Optional[datetime]

    class Constants(Filter.Constants):
        model = Gtfsdataset
