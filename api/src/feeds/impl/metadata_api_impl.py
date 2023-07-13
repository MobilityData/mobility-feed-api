from feeds_gen.apis.metadata_api_base import BaseMetadataApi
from feeds_gen.models.metadata import Metadata


class MetadataApiImpl(BaseMetadataApi):
    def metadata_get(
        self,
    ) -> Metadata:
        """Get metadata about this API."""
        return None