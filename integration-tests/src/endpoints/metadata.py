import re
import os

from endpoints.integration_tests import IntegrationTests


class BasicMetadataEndpointTests(IntegrationTests):
    """
    This class is used to perform basic tests on the metadata endpoint of the API.
    It will check if the format of the hash and version obtained from the API is correct.
    """

    def __init__(self, file_path, access_token, url, progress):
        super().__init__(file_path, access_token, url, progress=progress)

    @staticmethod
    def read_version_info_from_api(integrationTestsObject):
        """Test retrieval of GTFS feeds"""
        response = integrationTestsObject.get_response("v1/metadata")
        assert (
            response.status_code == 200
        ), f"Expected 200 status code for metadata, got {response.status_code}."
        metadata = response.json()
        api_version = metadata["version"]
        assert (
            api_version is not None
        ), f"Could not get proper version from API metadata = {metadata}"

        api_commit_hash = metadata["commit_hash"]
        assert (
            api_commit_hash is not None
        ), f"Could not get proper commit_hash from API metadata = {metadata}"

        return api_commit_hash, api_version

    def test_metadata(self):
        (
            api_commit_hash,
            api_version,
        ) = BasicMetadataEndpointTests.read_version_info_from_api(self)
        assert re.match(
            r"^v\d+\.\d+\.\d+.*$", api_version
        ), f"version from the API not the right format. version = {api_version}"

        # For the commit hash, it's safe to say it should be more than 20 characters.
        assert (
            len(api_commit_hash) > 20
        ), f"Commit hash from API seems too short  = {api_commit_hash}"


class MetadataEndpointTests(IntegrationTests):
    """
    This class is used to perform more detailed tests on the metadata endpoint of the API.
    It check if the hash and version from the API are the proper ones.
    Don't call this if the API and tests run on different versions.
    """

    def __init__(self, file_path, access_token, url, progress):
        super().__init__(file_path, access_token, url, progress=progress)
        self.version_info_path = os.path.join(
            os.path.dirname(__file__), "../../../api/src/version_info"
        )

    def read_version_info_from_file(self):
        """Read the version_info file and extract the long commit hash and extracted version"""
        with open(self.version_info_path, "r") as file:
            content = file.read()
            long_commit_hash = re.search(r"LONG_COMMIT_HASH=(\w+)", content).group(1)
            extracted_version = re.search(r"EXTRACTED_VERSION=(\S+)", content).group(1)
        return long_commit_hash, extracted_version

    def test_metadata(self):
        (
            api_commit_hash,
            api_version,
        ) = BasicMetadataEndpointTests.read_version_info_from_api(self)

        # Read the expected values from the version_info file
        (
            expected_long_commit_hash,
            expected_extracted_version,
        ) = self.read_version_info_from_file()

        # Verify that the commit hash matches the long commit hash from the version_info file
        assert api_commit_hash == expected_long_commit_hash, (
            f"Commit hash from metadata ({api_commit_hash}) does not match expected long commit hash "
            f"({expected_long_commit_hash})"
        )

        # Verify that the version matches the extracted version from the version_info file
        assert (
            api_version == expected_extracted_version
        ), f"Version from api ({api_version}) does not match expected extracted version ({expected_extracted_version})"
