from typing import List
from typing import Tuple

from sqlalchemy.orm import Query, Session

from shared.database.database import Database, with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsdataset,
    Feed,
)
from feeds.impl.error_handling import (
    raise_http_error,
)
from shared.common.error_handling import (
    dataset_not_found,
)
from shared.db_models.gtfs_dataset_impl import GtfsDatasetImpl
from feeds_gen.apis.datasets_api_base import BaseDatasetsApi
from feeds_gen.models.gtfs_dataset import GtfsDataset


class DatasetsApiImpl(BaseDatasetsApi):
    """
    This class represents the implementation of the `/datasets` endpoints.
    All methods from the parent class `feeds_gen.apis.datasets_api_base.BaseDatasetsApi` should be implemented.
    If a method is left blank the associated endpoint will return a 500 HTTP response.
    """

    @staticmethod
    def create_dataset_query() -> Query:
        return (
            Query(
                [
                    Gtfsdataset,
                    Gtfsdataset.bounding_box.ST_AsGeoJSON(),
                    Feed.stable_id,
                ]
            )
            .join(Feed, Feed.id == Gtfsdataset.feed_id)
            .order_by(Gtfsdataset.downloaded_at.desc())
        )

    @staticmethod
    def get_datasets_gtfs(query: Query, session: Session, limit: int = None, offset: int = None) -> List[GtfsDataset]:
        # Results are sorted by stable_id because Database.select(group_by=) requires it so
        dataset_groups = Database().select(
            session=session,
            query=query.order_by(Gtfsdataset.stable_id),
            limit=limit,
            offset=offset,
            group_by=lambda x: x[0].stable_id,
        )
        if not dataset_groups:
            return []
        gtfs_datasets = []
        for dataset_group in dataset_groups:
            dataset_objects: Tuple[Gtfsdataset, ...]
            dataset_objects, bound_box_strings, feed_ids = zip(*dataset_group)
            gtfs_datasets.append(GtfsDatasetImpl.from_orm(dataset_objects[0]))
        return gtfs_datasets

    @with_db_session
    def get_dataset_gtfs(self, id: str, db_session: Session) -> GtfsDataset:
        """Get the specified dataset from the Mobility Database."""

        query = DatasetsApiImpl.create_dataset_query().filter(Gtfsdataset.stable_id == id)

        if (ret := DatasetsApiImpl.get_datasets_gtfs(query, db_session)) and len(ret) == 1:
            return ret[0]
        else:
            raise_http_error(404, dataset_not_found.format(id))
