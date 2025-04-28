from endpoints.integration_tests import IntegrationTests


class GBFSFeedsEndpointTests(IntegrationTests):
    def __init__(self, file_path, access_token, url, progress):
        super().__init__(file_path, access_token, url, progress=progress)

    def test_gbfs_feeds_filter_by_provider(self):
        """Test retrieval of GBFS feeds filtered by provider"""
        providers = ["BIXI Montréal", "Bird Laval", "Lime Ottawa"]
        task_id = self.progress.add_task(
            "[yellow]Validating GTFS feeds by provider...[/yellow]",
            total=len(providers),
        )
        for i, provider_id in enumerate(providers):
            self._test_filter_by_provider(
                provider_id,
                "v1/gbfs_feeds",
                task_id=task_id,
                index=f"{i + 1}/{len(providers)}",
            )

    def test_gbfs_feeds_filter_by_version(self):
        """Test retrieval of GBFS feeds filtered by version"""
        versions = ["1.0", "2.3", "3.0"]
        task_id = self.progress.add_task(
            "[yellow]Validating GTFS feeds by version...[/yellow]",
            total=len(versions),
        )
        total_returned = 0
        for i, version in enumerate(versions):
            response = self.get_response(
                "v1/gbfs_feeds",
                params={"version": version},
            )
            assert (
                response.status_code == 200
            ), f"Expected 200 status code for version '{version}', got {response.status_code}."
            gbfs_feeds = response.json()
            total_returned += len(gbfs_feeds)
            self.console.log(
                ""
                f"Number of feeds returned for version '{version}': {len(gbfs_feeds)}"
            )
            self._update_progression(
                task_id,
                f"Retrieved feeds version {version}",
                f"{(i + 1)} / {len(versions)}",
            )
        assert (
            total_returned > 0
        ), f"No feeds returned for the specified versions: {versions}."

    def test_gbfs_feeds_filter_by_system_id(self):
        """Test retrieval of GBFS feeds filtered by system_id"""
        system_ids = ["bird-edmonton", "Bixi_MTL", "lime_ottawa"]
        task_id = self.progress.add_task(
            "[yellow]Validating GTFS feeds by system_id...[/yellow]",
            total=len(system_ids),
        )
        for i, system_id in enumerate(system_ids):
            response = self.get_response(
                "v1/gbfs_feeds",
                params={"system_id": system_id},
            )
            assert (
                response.status_code == 200
            ), f"Expected 200 status code for system_id '{system_id}', got {response.status_code}."
            gbfs_feeds = response.json()
            assert (
                len(gbfs_feeds) > 0
            ), f"No feeds returned for system_id '{system_id}'."
            self._update_progression(
                task_id,
                f"Retrieved feeds system_id {system_id}",
                f"{(i + 1)} / {len(system_ids)}",
            )
