from endpoints.integration_tests import IntegrationTests


class GTFSFeedsEndpointTests(IntegrationTests):
    def __init__(self, file_path, access_token, url, progress):
        super().__init__(file_path, access_token, url, progress=progress)

    def test_gtfs_feeds(self):
        """Test retrieval of GTFS feeds"""
        response = self.get_response("v1/gtfs_feeds", params={"limit": 100})
        assert (
            response.status_code == 200
        ), "Expected 200 status code for GTFS feeds, got {response.status_code}."
        gtfs_feeds = response.json()
        task_id = self.progress.add_task(
            "[yellow]Validating GTFS feeds type...[/yellow]", total=len(gtfs_feeds)
        )
        for i, feed in enumerate(gtfs_feeds):
            assert (
                feed["data_type"] == "gtfs"
            ), f"Expected data_type 'gtfs', got '{feed['data_type']}'."
            self.progress.update(
                task_id,
                advance=1,
                description=f"Validated GTFS feed {feed['id']} "
                f"({i + 1}/{len(gtfs_feeds)})",
            )

    def test_filter_by_country_code_gtfs(self):
        """Test GTFS feed retrieval filtered by country code"""
        country_codes = self._sample_country_codes(self.gtfs_feeds, 100)
        task_id = self.progress.add_task(
            "[yellow]Validating GTFS feeds by country code...[/yellow]",
            len(country_codes),
        )
        for i, country_code in enumerate(country_codes):
            self._test_filter_by_country_code(
                country_code,
                "v1/gtfs_feeds",
                validate_location=True,
                task_id=task_id,
                index=f"{i + 1}/{len(country_codes)}",
            )

    def test_filter_by_provider_gtfs(self):
        """Test GTFS feed retrieval filtered by provider"""
        providers = self.gtfs_feeds.provider.sample(100).values
        task_id = self.progress.add_task(
            "[yellow]Validating GTFS feeds by provider...[/yellow]",
            total=len(providers),
        )
        for i, provider_id in enumerate(providers):
            self._test_filter_by_provider(
                provider_id,
                "v1/gtfs_feeds",
                task_id=task_id,
                index=f"{i + 1}/{len(providers)}",
            )

    def test_filter_by_municipality_gtfs(self):
        """Test GTFS feed retrieval filter by municipality."""
        municipalities = self._sample_municipalities(self.gtfs_feeds, 100)
        task_id = self.progress.add_task(
            "[yellow]Validating GTFS feeds by municipality...[/yellow]",
            total=len(municipalities),
        )
        for i, municipality in enumerate(municipalities):
            self._test_filter_by_municipality(
                municipality,
                "v1/gtfs_feeds",
                validate_location=True,
                task_id=task_id,
                index=f"{i + 1}/{len(municipalities)}",
            )
