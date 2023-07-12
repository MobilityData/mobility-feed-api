from typing import ClassVar, Dict, List, Tuple

from feeds_gen.apis.datasets_api_base import BaseDatasetsApi
from feeds_gen.models.dataset import Dataset


class DatasetsApiImpl(BaseDatasetsApi):
    def datasets_gtfs_get(
            self,
            limit: int,
            offset: int,
            filter: str,
            sort: str,
            bounding_latitudes: str,
            bounding_longitudes: str,
            bounding_filter_method: str,
    ) -> List[Dataset]:
        return []
