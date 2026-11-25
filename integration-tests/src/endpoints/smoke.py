from endpoints.integration_tests import IntegrationTests


class SmokeEndpointTests(IntegrationTests):
    """Smoke tests for the deployed environments (QA and prod), run from integration-tests.yml.

    Checks that the main endpoints answer with real data for the few feeds in
    integration-tests/fixtures/smoke_sources.csv. Every endpoint is covered by the PR tests
    against the fixtures; this only confirms the deployment works.
    """

    def __init__(self, file_path, access_token, url, progress, console):
        super().__init__(file_path, access_token, url, progress, console)

    def _get_json(self, url_suffix, params=None):
        response = self.get_response(url_suffix, params=params)
        assert response.status_code == 200, (
            f"Expected 200 for {url_suffix} {params or ''}, got "
            f"{response.status_code}: {response.text[:300]}"
        )
        return response.json()

    def test_feeds_list(self):
        """GET /v1/feeds pages through the catalog."""
        feeds = self._get_json("v1/feeds", params={"limit": 10})
        assert len(feeds) == 10, f"Expected 10 feeds, got {len(feeds)}."

    def test_gtfs_feeds(self):
        """GET /v1/gtfs_feeds/{id} and its latest dataset, for each GTFS feed in the file."""
        for feed_id in self.gtfs_feeds.mdb_source_id:
            stable_id = f"mdb-{feed_id}"
            feed = self._get_json(f"v1/gtfs_feeds/{stable_id}")
            assert feed["id"] == stable_id
            latest = feed.get("latest_dataset")
            if latest:
                dataset = self._get_json(f"v1/datasets/gtfs/{latest['id']}")
                assert dataset["feed_id"] == stable_id

    def test_gtfs_rt_feeds(self):
        """GET /v1/gtfs_rt_feeds/{id}, for each GTFS-RT feed in the file."""
        for feed_id in self.gtfs_rt_feeds.mdb_source_id:
            stable_id = f"mdb-{feed_id}"
            assert self._get_json(f"v1/gtfs_rt_feeds/{stable_id}")["id"] == stable_id

    def test_gbfs_feeds(self):
        """GET /v1/gbfs_feeds returns feeds, each retrievable by id."""
        feeds = self._get_json("v1/gbfs_feeds", params={"limit": 1})
        assert feeds, "Expected at least one GBFS feed."
        assert self._get_json(f"v1/gbfs_feeds/{feeds[0]['id']}")["id"] == feeds[0]["id"]

    def test_search(self):
        """GET /v1/search finds a feed from the file by its provider."""
        row = self.gtfs_feeds.iloc[0]
        response = self._get_json(
            "v1/search", params={"search_query": row.provider, "limit": 100}
        )
        ids = {r["id"] for r in response["results"]}
        assert f"mdb-{row.mdb_source_id}" in ids, f"Got {ids}."

    def test_licenses(self):
        """GET /v1/licenses returns licenses."""
        assert self._get_json("v1/licenses", params={"limit": 1}), "Expected licenses."
