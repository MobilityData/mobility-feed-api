from shared.database_gen.sqlacodegen_models import Externalid
from feeds_gen.models.external_id import ExternalId


class ExternalIdImpl(ExternalId):
    """Implementation of the `ExternalId` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, external_id: Externalid | None) -> ExternalId | None:
        if not external_id:
            return None
        return cls(
            external_id=external_id.associated_id,
            source=external_id.source,
        )
