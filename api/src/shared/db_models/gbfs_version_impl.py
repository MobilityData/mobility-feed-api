from shared.db_models.gbfs_endpoint_impl import GbfsEndpointImpl
from shared.db_models.gbfs_validation_report_impl import GbfsValidationReportImpl
from feeds_gen.models.gbfs_version import GbfsVersion
from shared.database_gen.sqlacodegen_models import Gbfsversion as GbfsVersionOrm


class GbfsVersionImpl(GbfsVersion):
    """Implementation of the `GtfsFeed` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, version: GbfsVersionOrm | None) -> GbfsVersion | None:
        if not version:
            return None
        latest_report = (
            GbfsValidationReportImpl.from_orm(version.gbfsvalidationreports[0])
            if len(version.gbfsvalidationreports) > 0
            else None
        )
        return cls(
            version=version.version,
            created_at=version.created_at,
            last_updated_at=latest_report.validated_at if latest_report else None,
            source=version.source,
            endpoints=[GbfsEndpointImpl.from_orm(item) for item in version.gbfsendpoints]
            if version.gbfsendpoints
            else [],
            latest_validation_report=latest_report,
        )
