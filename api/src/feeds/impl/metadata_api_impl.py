import os

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

        try:
            # This file should be created by the github action right after checkout
            with open('version', 'r') as file:
                version = file.read().strip()
        except Exception as e:
            version = "N/A"

        try:
            # This file should be created by the github action right after checkout
            with open('commit_hash', 'r') as file:
                commit_hash = file.read().strip()
        except Exception as e:
            commit_hash = "N/A"

        return Metadata(version=version, commit_hash=commit_hash)
