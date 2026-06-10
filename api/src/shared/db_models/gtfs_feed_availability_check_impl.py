from shared.database_gen.sqlacodegen_models import GtfsFeedAvailabilityCheck as GtfsFeedAvailabilityCheckOrm
from feeds_gen.models.gtfs_feed_availability_check import GtfsFeedAvailabilityCheck

_REQUEST_TYPE_TO_METHOD = {"http_head": "HEAD", "http_get": "GET"}


class GtfsFeedAvailabilityCheckImpl(GtfsFeedAvailabilityCheck):
    """Implementation of the `GtfsFeedAvailabilityCheck` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, check: GtfsFeedAvailabilityCheckOrm | None) -> GtfsFeedAvailabilityCheck | None:
        """Create a model instance from a SQLAlchemy GtfsFeedAvailabilityCheck row object."""
        if not check:
            return None
        return cls(
            checked_at=check.checked_at,
            success=check.success,
            request_method=_REQUEST_TYPE_TO_METHOD.get(check.request_type, check.request_type),
            status_code=check.status_code,
            latency_ms=float(check.latency_ms) if check.latency_ms is not None else None,
            error_type=check.error_type,
        )
