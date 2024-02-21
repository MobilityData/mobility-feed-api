import re

from endpoints.integration_tests import IntegrationTests


class MetadataEndpointTests(IntegrationTests):
    def __init__(self, file_path, access_token, url, progress):
        super().__init__(file_path, access_token, url, progress=progress)

    def test_metadata(self):
        """Test retrieval of GTFS feeds"""
        response = self.get_response("v1/metadata")
        assert (
            response.status_code == 200
        ), "Expected 200 status code for metadata, got {response.status_code}."
        metadata = response.json()

        version = metadata["version"]
        assert (
            version is not None
        ), f"Could not extract version from metadata = {metadata}"

        assert re.match(
            r"^v\d+\.\d+\.\d+", version
        ), f"Found version but not the right format. metadata = {metadata}"

        commit_hash = metadata["commit_hash"]
        assert (
            commit_hash is not None
        ), f"Could not extract commit_hash from metadata = {metadata}"

        # For the commit hash, it's safe to say it should be more than 20 characters.
        assert (
            len(commit_hash) > 20
        ), f"Commit hash seems too short in metadata = {metadata}"
