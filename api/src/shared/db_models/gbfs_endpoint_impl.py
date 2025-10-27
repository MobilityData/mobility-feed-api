from feeds_gen.models.gbfs_endpoint import GbfsEndpoint
from shared.database_gen.sqlacodegen_models import Gbfsendpoint as GbfsEndpointOrm


class GbfsEndpointImpl(GbfsEndpoint):
    """Implementation of the `GtfsFeed` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, endpoint: GbfsEndpointOrm | None) -> GbfsEndpoint | None:
        if not endpoint:
            return None
        return cls(name=endpoint.name, url=endpoint.url, language=endpoint.language, is_feature=endpoint.is_feature)
