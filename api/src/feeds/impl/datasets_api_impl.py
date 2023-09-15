import json
from typing import List

from fastapi import HTTPException
from geoalchemy2 import WKTElement
from sqlalchemy import or_
from sqlalchemy.orm import Query

from database.database import Database
from database_gen.sqlacodegen_models import Gtfsdataset, t_componentgtfsdataset, Feed
from feeds_gen.apis.datasets_api_base import BaseDatasetsApi
from feeds_gen.models.bounding_box import BoundingBox
from feeds_gen.models.gtfs_dataset import GtfsDataset


class DatasetsApiImpl(BaseDatasetsApi):
    """
    This class represents the implementation of the `/datasets` endpoints.
    All methods from the parent class `feeds_gen.apis.datasets_api_base.BaseDatasetsApi` should be implemented.
    If a method is left blank the associated endpoint will return a 500 HTTP response.
    """

    @staticmethod
    def create_dataset_query():
        return (Query([Gtfsdataset, t_componentgtfsdataset.c['component'],
                       Gtfsdataset.bounding_box.ST_AsGeoJSON(), Feed.stable_id])
                .join(t_componentgtfsdataset, t_componentgtfsdataset.c['dataset_id'] == Gtfsdataset.id, isouter=True)
                .join(Feed, Feed.id == Gtfsdataset.feed_id))

    @staticmethod
    def apply_bounding_filtering(query: Query, bounding_latitudes: str, bounding_longitudes: str,
                                 bounding_filter_method: str) -> Query:
        """Create a new query based on the bounding parameters."""

        if not bounding_latitudes or not bounding_longitudes or not bounding_filter_method:
            return query

        if len(bounding_latitudes_tokens := bounding_latitudes.split(",")) != 2 or len(
                bounding_longitudes_tokens := bounding_longitudes.split(",")) != 2:
            raise HTTPException(status_code=400,
                                detail=f"Invalid bounding coordinates {bounding_latitudes} {bounding_longitudes}")
        min_latitude, max_latitude = bounding_latitudes_tokens
        min_longitude, max_longitude = bounding_longitudes_tokens

        bounding_box = WKTElement(
            f"POLYGON(({min_longitude} {min_latitude}, {max_longitude} {min_latitude}, {max_longitude} {max_latitude}, "
            f"{min_longitude} {max_latitude}, {min_longitude} {min_latitude}))",
            srid=Gtfsdataset.bounding_box.type.srid)

        if bounding_filter_method == "partially_enclosed":
            return query.filter(or_(Gtfsdataset.bounding_box.ST_Overlaps(bounding_box),
                                    Gtfsdataset.bounding_box.ST_Contains(bounding_box)))
        elif bounding_filter_method == "completely_enclosed":
            return query.filter(Gtfsdataset.bounding_box.ST_Covers(bounding_box))
        elif bounding_filter_method == "disjoint":
            return query.filter(Gtfsdataset.bounding_box.ST_Disjoint(bounding_box))
        else:
            raise HTTPException(status_code=400, detail=f"Invalid bounding_filter_method {bounding_filter_method}")

    @staticmethod
    def get_datasets_gtfs(query: Query, limit: int = None, offset: int = None) -> List[GtfsDataset]:
        # Results are sorted by stable_id because Database.select(group_by=) requires it so
        dataset_groups = Database().select(query=query.order_by(Gtfsdataset.stable_id),
                                           limit=limit, offset=offset, group_by=lambda x: x[0].stable_id)

        gtfs_datasets = []
        for dataset_group in dataset_groups:
            dataset_objects, components, bound_box_strings, feed_ids = zip(*dataset_group)
            database_gtfs_dataset = dataset_objects[0]
            gtfs_dataset = GtfsDataset(id=database_gtfs_dataset.stable_id,
                                       feed_id=feed_ids[0],
                                       hosted_url=database_gtfs_dataset.hosted_url,
                                       note=database_gtfs_dataset.note,
                                       downloaded_at=database_gtfs_dataset.download_date.isoformat()
                                       if database_gtfs_dataset.download_date else None,
                                       hash=database_gtfs_dataset.hash,
                                       components=[component for component in components if component is not None])

            if bound_box_string := bound_box_strings[0]:
                coordinates = json.loads(bound_box_string)['coordinates'][0]
                gtfs_dataset.bounding_box = BoundingBox(
                    minimum_latitude=coordinates[0][1],
                    maximum_latitude=coordinates[2][1],
                    minimum_longitude=coordinates[0][0],
                    maximum_longitude=coordinates[2][0], )
            gtfs_datasets.append(gtfs_dataset)
        return gtfs_datasets

    def get_dataset_gtfs(
            self,
            id: str,
    ) -> GtfsDataset:
        """Get the specified dataset from the Mobility Database."""

        query = DatasetsApiImpl.create_dataset_query().filter(Gtfsdataset.stable_id == id)

        if (ret := DatasetsApiImpl.get_datasets_gtfs(query)) and len(ret) == 1:
            return ret[0]
        else:
            raise HTTPException(status_code=404, detail=f"Dataset {id} not found")
