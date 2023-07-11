# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from feeds_gen.models.dataset import Dataset
from feeds_gen.security_api import get_token_ApiKeyAuth

class BaseDatasetsApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseDatasetsApi.subclasses = BaseDatasetsApi.subclasses + (cls,)
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
        """Get some (or all) GTFS datasets from the Mobility Database."""
        ...


    def datasets_gtfs_id_get(
        self,
        id: str,
    ) -> Dataset:
        """Get the specified dataset in the Mobility Database."""
        ...


    def feeds_gtfs_id_datasets_get(
        self,
        id: str,
        latest: bool,
        limit: int,
        offset: int,
        filter: str,
        sort: str,
        bounding_latitudes: str,
        bounding_longitudes: str,
        bounding_filter_method: str,
    ) -> List[Dataset]:
        """Get a list of datasets related to a feed."""
        ...
