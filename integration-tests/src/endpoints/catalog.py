import json
import os

from endpoints.integration_tests import IntegrationTests

# The PR workflow seeds the database from these fixtures, so the tests can expect their exact
# values. Not meant for the deployed environments, which run SmokeEndpointTests instead.
FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "fixtures"
)  # integration-tests/fixtures

# Fixture feeds the tests below are written against (integration-tests/fixtures/sources.csv).
FEED_WITH_DATASETS = (
    "mdb-745"  # 2 datasets, a validation report, availability checks, a seal
)
FEED_WITH_ONE_DATASET = "mdb-935"
RT_FEED = "mdb-1366"  # GTFS-RT trip updates referencing mdb-745
GBFS_FEED = "gbfs-Bixi_MTL"


class CatalogEndpointTests(IntegrationTests):
    """Every Feeds API endpoint, checked against the data in integration-tests/fixtures."""

    def __init__(self, file_path, access_token, url, progress, console):
        super().__init__(file_path, access_token, url, progress, console)
        with open(os.path.join(FIXTURES_DIR, "test_data.json")) as f:
            self.test_data = json.load(f)

    def _get_json(self, url_suffix, params=None, expected_status=200):
        response = self.get_response(url_suffix, params=params)
        assert response.status_code == expected_status, (
            f"Expected {expected_status} for {url_suffix} {params or ''}, got "
            f"{response.status_code}: {response.text[:300]}"
        )
        return response.json()

    def _datasets_of(self, stable_id):
        return [
            d for d in self.test_data["datasets"] if d["feed_stable_id"] == stable_id
        ]

    def test_gtfs_feed_by_id(self):
        """GET /v1/gtfs_feeds/{id} returns the feed with its latest dataset."""
        feed = self._get_json(f"v1/gtfs_feeds/{FEED_WITH_DATASETS}")
        assert feed["id"] == FEED_WITH_DATASETS
        assert feed["data_type"] == "gtfs"
        latest = next(d for d in self._datasets_of(FEED_WITH_DATASETS) if d["latest"])
        assert (
            feed["latest_dataset"]["id"] == latest["id"]
        ), f"Expected latest dataset {latest['id']}, got {feed['latest_dataset']}."
        assert feed["source_info"]["license_id"] == "CC-BY-4.0"

    def test_gtfs_rt_feed_by_id(self):
        """GET /v1/gtfs_rt_feeds/{id} returns the feed with its schedule references."""
        feed = self._get_json(f"v1/gtfs_rt_feeds/{RT_FEED}")
        assert feed["id"] == RT_FEED
        assert feed["data_type"] == "gtfs_rt"
        assert feed["entity_types"] == ["tu"], f"Got {feed['entity_types']}."
        assert feed["feed_references"] == [FEED_WITH_DATASETS]

    def test_gbfs_feed_by_id(self):
        """GET /v1/gbfs_feeds/{id} returns the feed with its versions."""
        feed = self._get_json(f"v1/gbfs_feeds/{GBFS_FEED}")
        assert feed["id"] == GBFS_FEED
        assert feed["system_id"] == "Bixi_MTL"
        versions = sorted(v["version"] for v in feed["versions"])
        assert versions == ["1.0", "2.2"], f"Got versions {versions}."

    def test_gtfs_feed_gtfs_rt_feeds(self):
        """GET /v1/gtfs_feeds/{id}/gtfs_rt_feeds returns the RT feeds referencing the feed."""
        rt_feeds = self._get_json(f"v1/gtfs_feeds/{FEED_WITH_DATASETS}/gtfs_rt_feeds")
        ids = sorted(feed["id"] for feed in rt_feeds)
        assert ids == ["mdb-1366", "mdb-1367", "mdb-1368"], f"Got {ids}."

    def test_gtfs_feed_datasets(self):
        """GET /v1/gtfs_feeds/{id}/datasets lists the datasets, newest first; latest=true only the latest."""
        expected = sorted(
            self._datasets_of(FEED_WITH_DATASETS),
            key=lambda d: d["downloaded_at"],
            reverse=True,
        )
        datasets = self._get_json(f"v1/gtfs_feeds/{FEED_WITH_DATASETS}/datasets")
        assert [d["id"] for d in datasets] == [d["id"] for d in expected]
        assert all(d["feed_id"] == FEED_WITH_DATASETS for d in datasets)

        latest = self._get_json(
            f"v1/gtfs_feeds/{FEED_WITH_DATASETS}/datasets", params={"latest": True}
        )
        assert [d["id"] for d in latest] == [
            next(d["id"] for d in expected if d["latest"])
        ]

    def test_dataset_by_id(self):
        """GET /v1/datasets/gtfs/{id} returns the dataset and its validation report."""
        report = self.test_data["validation_reports"][0]
        dataset = self._get_json(f"v1/datasets/gtfs/{report['dataset_id']}")
        assert dataset["id"] == report["dataset_id"]
        assert dataset["feed_id"] == FEED_WITH_DATASETS
        assert dataset["validation_report"]["total_error"] == report["total_error"]
        assert dataset["validation_report"]["features"] == ["Shapes"]

    def test_gtfs_feed_validation_reports(self):
        """GET /v1/gtfs_feeds/{id}/validation_reports returns the reports and their notices."""
        expected = self.test_data["validation_reports"][0]
        response = self._get_json(
            f"v1/gtfs_feeds/{FEED_WITH_DATASETS}/validation_reports"
        )
        assert response["feed_id"] == FEED_WITH_DATASETS
        assert response["total"] == 1, f"Expected 1 report, got {response['total']}."
        report = response["items"][0]
        assert report["dataset_id"] == expected["dataset_id"]
        assert report["total_warning"] == expected["total_warning"]
        codes = sorted(n["code"] for n in report.get("notices") or [])
        assert codes == sorted(
            n["notice_code"] for n in self.test_data["notices"]
        ), f"Got notices {codes}."

        filtered = self._get_json(
            f"v1/gtfs_feeds/{FEED_WITH_DATASETS}/validation_reports",
            params={"min_errors": expected["total_error"] + 1},
        )
        assert (
            filtered["total"] == 0
        ), "min_errors above the report's errors should filter it out."

    def test_gtfs_feed_availability(self):
        """GET /v1/gtfs_feeds/{id}/availability returns only availability checks, newest first."""
        expected = [
            c
            for c in self.test_data["gtfs_availability_checks"]
            if c["feed_stable_id"] == FEED_WITH_DATASETS
            and c.get("source", "availability_check") == "availability_check"
        ]
        response = self._get_json(f"v1/gtfs_feeds/{FEED_WITH_DATASETS}/availability")
        assert response["feed_id"] == FEED_WITH_DATASETS
        assert response["total"] == len(expected), (
            f"Expected {len(expected)} checks (dataset_download_manual excluded), got "
            f"{response['total']}."
        )
        checked_at = [c["checked_at"] for c in response["checks"]]
        assert checked_at == sorted(checked_at, reverse=True), "Expected newest first."
        assert [c["success"] for c in response["checks"]] == [True, False, True]

    def test_gtfs_feed_reliability(self):
        """GET /v1/gtfs_feeds/{id}/reliability returns the seal and all six criteria."""
        report = self._get_json(f"v1/gtfs_feeds/{FEED_WITH_DATASETS}/reliability")
        assert report["feed_id"] == FEED_WITH_DATASETS
        assert report["has_seal"] is True
        statuses = {c["criterion"]: c["status"] for c in report["criteria"]}
        assert len(statuses) == 6, f"Expected 6 criteria, got {list(statuses)}."
        assert statuses["official"] == "pass"
        assert statuses["stable"] == "never_evaluated"

        unsealed = self._get_json(f"v1/gtfs_feeds/{FEED_WITH_ONE_DATASET}/reliability")
        assert unsealed["has_seal"] is False

    def test_gtfs_feed_continuous_coverage(self):
        """GET /v1/gtfs_feeds/{id}/continuous_coverage returns one item per dataset."""
        response = self._get_json(
            f"v1/gtfs_feeds/{FEED_WITH_DATASETS}/continuous_coverage"
        )
        assert response["feed_id"] == FEED_WITH_DATASETS
        assert response["total"] == len(self._datasets_of(FEED_WITH_DATASETS))
        latest = [item["dataset_id"] for item in response["items"] if item["is_latest"]]
        assert latest == ["mdb-745-202603010000"], f"Got latest {latest}."

    def test_search(self):
        """GET /v1/search finds feeds by provider and filters by data type."""
        response = self._get_json(
            "v1/search", params={"search_query": "Exo Haut-Saint-Laurent"}
        )
        ids = {r["id"] for r in response["results"]}
        assert {"mdb-745", "mdb-1366", "mdb-1367", "mdb-1368"} <= ids, f"Got {ids}."

        gtfs_only = self._get_json(
            "v1/search",
            params={"search_query": "Exo Haut-Saint-Laurent", "data_type": "gtfs"},
        )
        assert {r["id"] for r in gtfs_only["results"]} == {"mdb-745"}

    def test_locations(self):
        """GET /v1/locations searches the geopolygons and resolves their country and subdivision."""
        response = self._get_json("v1/locations", params={"search_query": "Montreal"})
        names = [r["name"] for r in response["results"]]
        assert "Montréal" in names, f"Got {names}."
        montreal = next(r for r in response["results"] if r["name"] == "Montréal")
        assert montreal["location_type"] == "municipality"
        assert montreal["country_code"] == "CA"
        assert montreal["subdivision_code"] == "CA-QC"

        countries = self._get_json("v1/locations", params={"location_type": "country"})
        assert sorted(r["country_code"] for r in countries["results"]) == ["AU", "CA"]

    def test_licenses(self):
        """GET /v1/licenses lists the licenses; GET /v1/licenses/{id} returns one with its rules."""
        licenses = self._get_json("v1/licenses")
        assert sorted(lic["id"] for lic in licenses) == sorted(
            lic["id"] for lic in self.test_data["licenses"]
        )

        apache = self._get_json("v1/licenses/Apache-2.0")
        rules = sorted((r["name"], r["type"]) for r in apache["license_rules"])
        # patent-use exists as both a permission and a limitation; Apache-2.0 has the permission.
        assert rules == [
            ("commercial-use", "permission"),
            ("patent-use", "permission"),
        ], f"Got rules {rules}."

    def test_licenses_match(self):
        """POST /v1/licenses:match resolves an exact URL and a Creative Commons variant."""
        response = self.send_request(
            "POST",
            "v1/licenses:match",
            json={"license_url": "https://www.apache.org/licenses/LICENSE-2.0"},
        )
        assert (
            response.status_code == 200
        ), f"Got {response.status_code}: {response.text}"
        matches = response.json()
        assert matches and matches[0]["license_id"] == "Apache-2.0"
        assert matches[0]["match_type"] == "exact"

        response = self.send_request(
            "POST",
            "v1/licenses:match",
            json={"license_url": "https://creativecommons.org/licenses/by/4.0/deed.nl"},
        )
        assert (
            response.status_code == 200
        ), f"Got {response.status_code}: {response.text}"
        assert [m["license_id"] for m in response.json()][:1] == ["CC-BY-4.0"]
