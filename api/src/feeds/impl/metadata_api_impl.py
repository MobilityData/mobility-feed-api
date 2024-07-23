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

            # The version_info file is in api/src subdirectory. We're not sure which directory this code is running
            # (and it's different for tests), but we will assume api is in the path.
            current_directory = os.getcwd()

            root_directory = current_directory.split("/api", 1)[0]
            if root_directory is None:
                raise Exception(
                    "Cannot find version_info file. "
                    + f"Cannot find api in the path to the current working directory = {current_directory}"
                )
            file = root_directory + "/api/src/version_info"

            # Read the properties file. This file should have been filled as part of the build.
            config.read(file)

            # Access the values using the get() method
            long_commit_hash = config.get("DEFAULT", "LONG_COMMIT_HASH")
            version = config.get("DEFAULT", "EXTRACTED_VERSION")

        except Exception as e:
            logging.error(f"Cannot read {file} file from directory {current_directory}: \n {e}")

        return Metadata(version=version, commit_hash=long_commit_hash)
