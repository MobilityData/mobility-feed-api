import re
import os

from endpoints.integration_tests import IntegrationTests


class BasicMetadataEndpointTests(IntegrationTests):
    def __init__(self, file_path, access_token, url, progress):
        super().__init__(file_path, access_token, url, progress=progress)
        self.version_info_path = os.path.join(
            os.path.dirname(__file__), "../../../api/src/version_info"
        )

    def read_version_info(self):
        """Read the version_info file and extract the long commit hash and extracted version"""
        with open(self.version_info_path, "r") as file:
            content = file.read()
            long_commit_hash = re.search(r"LONG_COMMIT_HASH=(\w+)", content).group(1)
            extracted_version = re.search(r"EXTRACTED_VERSION=(\S+)", content).group(1)
        return long_commit_hash, extracted_version

    def test_metadata(self):
        """Test retrieval of GTFS feeds"""
        response = self.get_response("v1/metadata")
        assert (
            response.status_code == 200
        ), f"Expected 200 status code for metadata, got {response.status_code}."
        metadata = response.json()

        version = metadata["version"]
        assert (
            version is not None
        ), f"Could not extract version from metadata = {metadata}"

        assert re.match(
            r"^v\d+\.\d+\.\d+(_SNAPSHOT)?$", version
        ), f"Found version but not the right format. metadata = {metadata}"

        commit_hash = metadata["commit_hash"]
        assert (
            commit_hash is not None
        ), f"Could not extract commit_hash from metadata = {metadata}"

        # For the commit hash, it's safe to say it should be more than 20 characters.
        assert (
            len(commit_hash) > 20
        ), f"Commit hash seems too short in metadata = {metadata}"


class MetadataEndpointTests(IntegrationTests):
    def __init__(self, file_path, access_token, url, progress):
        super().__init__(file_path, access_token, url, progress=progress)
        self.version_info_path = os.path.join(
            os.path.dirname(__file__), "../../../api/src/version_info"
        )

    def read_version_info(self):
        """Read the version_info file and extract the long commit hash and extracted version"""
        with open(self.version_info_path, "r") as file:
            content = file.read()
            long_commit_hash = re.search(r"LONG_COMMIT_HASH=(\w+)", content).group(1)
            extracted_version = re.search(r"EXTRACTED_VERSION=(\S+)", content).group(1)
        return long_commit_hash, extracted_version

    def test_metadata(self):
        """Test retrieval of GTFS feeds"""
        response = self.get_response("v1/metadata")
        assert (
            response.status_code == 200
        ), f"Expected 200 status code for metadata, got {response.status_code}."
        metadata = response.json()

        version = metadata["version"]
        assert (
            version is not None
        ), f"Could not extract version from metadata = {metadata}"

        commit_hash = metadata["commit_hash"]
        assert (
            commit_hash is not None
        ), f"Could not extract commit_hash from metadata = {metadata}"

        # Read the expected values from the version_info file
        expected_long_commit_hash, expected_extracted_version = self.read_version_info()
        expected_extracted_version += "Allo"

        # Verify that the commit hash matches the long commit hash from the version_info file
        assert commit_hash == expected_long_commit_hash, (
            f"Commit hash from metadata ({commit_hash}) does not match expected long commit hash "
            f"({expected_long_commit_hash})"
        )

        # Verify that the version matches the extracted version from the version_info file
        assert (
            version == expected_extracted_version
        ), f"Version from metadata ({version}) does not match expected extracted version ({expected_extracted_version})"
