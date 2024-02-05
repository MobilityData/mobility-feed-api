import numpy
import pandas

from endpoints.integration_tests import IntegrationTests


class FeedsEndpointTests(IntegrationTests):
    def __init__(self, file_path, access_token, url, progress):
        super().__init__(file_path, access_token, url, progress=progress)

    def test_feeds_id(self):
        """Test retrieval of specific feed by ID"""
        stable_id = 'mdb-100'
        response = self.get_response(f'v1/feeds/{stable_id}')
        assert response.status_code == 200, (f"Expected 200 status code for stable_id '{stable_id}', got "
                                             f"{response.status_code}.")
        feed = response.json()
        assert feed['id'] == stable_id, f"Expected feed ID '{stable_id}', got '{feed['id']}'."

    def test_feeds_default(self):
        """Test default feed retrieval"""
        response = self.get_response('v1/feeds')
        assert response.status_code == 200, f"Expected 200 status code, got {response.status_code}."
        assert isinstance(response.json(), list), "Response should be a list."
        assert len(response.json()) > 0, "Expected non-empty list of feeds."

    def test_feeds_limit(self):
        """Test feed retrieval with limit"""
        response = self.get_response('v1/feeds', {'limit': 10})
        assert response.status_code == 200, f"Expected 200 status code, got {response.status_code}."
        feeds = response.json()
        assert isinstance(feeds, list), "Response should be a list."
        assert len(feeds) == 10, f"Expected 10 feeds, got {len(feeds)}."

    def test_feeds_offset(self):
        """Test feed retrieval with offset"""
        limit = 10
        response = self.get_response('v1/feeds', {'limit': limit})
        assert response.status_code == 200, f"Expected 200 status code for initial request, got {response.status_code}."
        initial_feeds = response.json()
        assert isinstance(initial_feeds, list), "Initial response should be a list."
        assert len(initial_feeds) == limit, f"Expected {limit} feeds initially, got {len(initial_feeds)}."

        prev_feeds_ids = [feed["id"] for feed in initial_feeds]
        response = self.get_response('v1/feeds', {'offset': limit})
        assert response.status_code == 200, (f"Expected 200 status code for offset request, got "
                                             f"{response.status_code}.")
        offset_feeds = response.json()
        assert isinstance(offset_feeds, list), "Offset response should be a list."
        for feed in offset_feeds:
            assert feed["id"] not in prev_feeds_ids, f"Feed ID '{feed['id']}' should not appear in previous set."

    def test_feeds_with_status(self):
        """Test feed retrieval by status"""
        for status in ["active", "inactive", "deprecated", "development"]:
            response = self.get_response('v1/feeds', params={"status": status})
            assert response.status_code == 200, (f"Expected 200 status code for status '{status}', got "
                                                 f"{response.status_code}.")
            for feed in response.json():
                assert feed["status"] == status, f"Expected status '{status}', got '{feed['status']}'."

    def test_feeds_status_sorting_descending(self):
        """Test sorting of feeds on status in descending order"""
        response = self.get_response('v1/feeds', params={"sort": "-status"})
        assert response.status_code == 200, f"Expected 200 status code for sorted feeds, got {response.status_code}."
        feeds = response.json()
        assert len(feeds) > 1, "Expected more than one feed for sorting test."
        prev_feed_status = feeds[0]["status"]
        for feed in feeds[1:]:
            current_feed_status = feed["status"]
            assert current_feed_status <= prev_feed_status, (
                f"Expected feed status to be in descending order, but found '{prev_feed_status}' followed by "
                f"'{current_feed_status}'."
            )
            prev_feed_status = current_feed_status

    def test_feeds_status_sorting_ascending(self):
        """Test sorting of feeds on status in ascending order"""
        response = self.get_response('v1/feeds', params={"sort": "+status"})
        assert response.status_code == 200, f"Expected 200 status code for sorted feeds, got {response.status_code}."
        feeds = response.json()
        assert len(feeds) > 1, "Expected more than one feed for sorting test."
        prev_feed_status = feeds[0]["status"]
        for feed in feeds[1:]:
            current_feed_status = feed["status"]
            assert current_feed_status >= prev_feed_status, (
                f"Expected feed status to be in ascending order, but found '{prev_feed_status}' followed by "
                f"'{current_feed_status}'."
            )
            prev_feed_status = current_feed_status

    def test_filter_by_country_code(self):
        """Test feed retrieval filtered by country code"""
        df = pandas.concat([self.gtfs_feeds, self.gtfs_rt_feeds], ignore_index=True)
        country_codes = self._sample_country_codes(df, 20)
        task_id = self.progress.add_task("[yellow]Validating feeds by country code...[/yellow]", total=len(country_codes))
        for i, country_code in enumerate(country_codes):
            self._test_filter_by_country_code(country_code, 'v1/feeds', task_id=task_id,
                                              index=f'{i + 1}/{len(country_codes)}')

    def test_filter_by_provider(self):
        """Test feed retrieval filtered by provider"""
        providers = self.gtfs_feeds.provider.sample(10).values
        providers = numpy.append(providers, self.gtfs_rt_feeds.provider.sample(10).values)
        task_id = self.progress.add_task("[yellow]Validating feeds by provider...[/yellow]", total=len(providers))
        for i, provider_id in enumerate(providers):
            self._test_filter_by_provider(provider_id, 'v1/feeds', task_id=task_id,
                                          index=f'{i + 1}/{len(providers)}')

    def test_filter_by_municipality(self):
        """Test feed retrieval filter by municipality."""
        df = pandas.concat([self.gtfs_feeds, self.gtfs_rt_feeds], ignore_index=True)
        municipalities = self._sample_municipalities(df, 20)
        task_id = self.progress.add_task("[yellow]Validating feeds by municipality...[/yellow]",
                                         total=len(municipalities))
        for i, municipality in enumerate(municipalities):
            self._test_filter_by_municipality(municipality, 'v1/feeds', task_id=task_id,
                                              index=f'{i + 1}/{len(municipalities)}')
