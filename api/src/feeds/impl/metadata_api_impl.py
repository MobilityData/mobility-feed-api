from feeds_gen.apis.metadata_api_base import BaseMetadataApi
from feeds_gen.models.metadata import Metadata


class MetadataApiImpl(BaseMetadataApi):
    """
    This class represents the implementation of the `/datasets` endpoints.
    All methods from the parent class `feeds_gen.apis.metadata_api_base.BaseMetadataApi` should be implemented.
    If a method is left blank the associated endpoint will return a 500 HTTP response.
    """

    def get_metadata(
        self,
    ) -> Metadata:
        """Get metadata about this API."""
        return Metadata(version="1.0.0")
