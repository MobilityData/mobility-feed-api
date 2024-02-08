from endpoints.integration_tests import IntegrationTests


class GTFSRTFeedsEndpointTests(IntegrationTests):
    def __init__(self, file_path, access_token, url, progress):
        super().__init__(file_path, access_token, url, progress=progress)

    def test_filter_by_provider_gtfs_rt(self):
        """Test GTFS Realtime feed retrieval filtered by provider"""
        providers = self.gtfs_rt_feeds.provider.sample(100).values
        task_id = self.progress.add_task(
            "[yellow]Validating GTFS Realtime feeds by provider...[/yellow]",
            total=len(providers),
        )

        for i, provider_id in enumerate(providers):
            self._test_filter_by_provider(
                provider_id,
                "v1/gtfs_rt_feeds",
                task_id=task_id,
                index=f"{i + 1}/{len(providers)}",
            )

    def test_filter_by_country_code_gtfs_rt(self):
        """Test GTFS Realtime feed retrieval filtered by country code"""
        country_codes = self._sample_country_codes(self.gtfs_feeds, 100)
        task_id = self.progress.add_task(
            "[yellow]Validating GTFS Realtime feeds by country code...[/yellow]",
            total=len(country_codes),
        )

        for i, country_code in enumerate(country_codes):
            self._test_filter_by_country_code(
                country_code,
                "v1/gtfs_rt_feeds",
                task_id=task_id,
                index=f"{i + 1}/{len(country_codes)}",
            )

    def test_filter_by_municipality_gtfs_rt(self):
        """Test GTFS Realtime feed retrieval filter by municipality."""
        municipalities = self._sample_municipalities(self.gtfs_rt_feeds, 100)
        task_id = self.progress.add_task(
            "[yellow]Validating GTFS Realtime feeds by municipality...[/yellow]",
            total=len(municipalities),
        )
        for i, municipality in enumerate(municipalities):
            self._test_filter_by_municipality(
                municipality,
                "v1/gtfs_rt_feeds",
                task_id=task_id,
                index=f"{i + 1}/{len(municipalities)}",
            )
