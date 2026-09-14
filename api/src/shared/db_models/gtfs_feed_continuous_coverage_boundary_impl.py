from typing import Optional

from feeds_gen.models.gtfs_feed_continuous_coverage_boundary import GtfsFeedContinuousCoverageBoundary
from shared.database_gen.sqlacodegen_models import Gtfsdataset as GtfsdatasetOrm
from shared.db_models.gtfs_feed_continuous_coverage_impl import GtfsFeedContinuousCoverageImpl


class GtfsFeedContinuousCoverageBoundaryImpl(GtfsFeedContinuousCoverageBoundary):
    """Implementation of the `GtfsFeedContinuousCoverageBoundary` model."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(
        cls,
        dataset: Optional[GtfsdatasetOrm],
        previous_dataset: Optional[GtfsdatasetOrm] = None,
        is_latest: bool = False,
    ) -> Optional[GtfsFeedContinuousCoverageBoundary]:
        """Both datasets of one boundary: `dataset` and the one downloaded before it.

        `previous_dataset` is passed in rather than looked up here because it may sit outside the
        requested page - only the caller knows the unpaged neighbour.
        """
        if dataset is None:
            return None
        return cls(
            newer=GtfsFeedContinuousCoverageImpl.from_orm(
                dataset, previous_dataset=previous_dataset, is_latest=is_latest
            ),
            older=GtfsFeedContinuousCoverageImpl.from_orm(previous_dataset),
        )
