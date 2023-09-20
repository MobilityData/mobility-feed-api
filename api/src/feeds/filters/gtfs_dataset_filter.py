from typing import Optional
from datetime import datetime
from fastapi_filter.contrib.sqlalchemy import Filter

from database_gen.sqlacodegen_models import Gtfsdataset


class GtfsDatasetFilter(Filter):
    download_date__lte: Optional[datetime]
    download_date__gte: Optional[datetime]

    class Constants(Filter.Constants):
        model = Gtfsdataset
