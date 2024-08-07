import configparser
import logging
import os

from feeds_gen.apis.metadata_api_base import BaseMetadataApi
from feeds_gen.models.metadata import Metadata


class MetadataApiImpl(BaseMetadataApi):
    """
    This class represents the implementation of the `/metadata` endpoint.
    All methods from the parent class `feeds_gen.apis.metadata_api_base.BaseMetadataApi` should be implemented.
    If a method is left blank the associated endpoint will return a 500 HTTP response.
    """

    def get_metadata(
        self,
    ) -> Metadata:
        """Get metadata about this API."""
        version = None
        long_commit_hash = None
        try:
            # Create a configparser object
            config = configparser.ConfigParser()

            current_directory = os.getcwd()

            file = "version_info"
            # The config file is on api/src. Normally the cwd is api/src, but with unit tests it's api. In that case
            # add /src
            if current_directory.endswith("api"):
                file = os.path.join("src", file)

            # Read the properties file. This file should have been filled as part of the build.
            config.read(file)

            # Access the values using the get() method
            long_commit_hash = config.get("DEFAULT", "LONG_COMMIT_HASH")
            version = config.get("DEFAULT", "EXTRACTED_VERSION")

        except Exception as e:
            logging.error(f"Cannot read {file} file from directory {current_directory}: \n {e}")

        return Metadata(version=version, commit_hash=long_commit_hash)
