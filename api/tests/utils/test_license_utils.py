"""Unit tests for license_utils module."""
import unittest
from unittest.mock import MagicMock, patch

from shared.common.license_utils import (
    extract_host,
    resolve_commons_creative_license,
    heuristic_spdx,
    fuzzy_ratio,
    resolve_fuzzy_match,
    resolve_license,
    find_exact_match_license_url,
    assign_license_by_url,
    MatchingLicense,
)
from shared.database_gen.sqlacodegen_models import License


class TestLicenseUtils(unittest.TestCase):
    """Test cases for license-related helper functions."""

    def setUp(self):
        self.session = MagicMock()

    # --- extract_host ---
    def test_extract_host_basic(self):
        self.assertEqual(extract_host("example.com/path/to"), "example.com")
        self.assertEqual(extract_host("example.com"), "example.com")
        self.assertEqual(extract_host("http://example.com"), "example.com")
        self.assertEqual(extract_host(" https://example.com"), "example.com")
        self.assertEqual(extract_host(""), "")

    # --- resolve_commons_creative_license ---
    def test_resolve_commons_creative_license_cc0(self):
        url = "https://creativecommons.org/publicdomain/zero/1.0/"
        spdx, note, regional_id = resolve_commons_creative_license(url)
        self.assertEqual(spdx, "CC0-1.0")
        self.assertIsNone(note)
        self.assertIsNone(regional_id)

    def test_resolve_commons_creative_license_by_variants(self):
        # BY with deed / legalcode suffixes and locale code
        urls = [
            "https://creativecommons.org/licenses/by/4.0/",
            "https://creativecommons.org/licenses/by/4.0/deed.en",
            "https://creativecommons.org/licenses/by/4.0/legalcode",
        ]
        for u in urls:
            spdx, note, regional_id = resolve_commons_creative_license(u)
            self.assertEqual(spdx, "CC-BY-4.0")
            self.assertIsNone(note)
            self.assertIsNone(regional_id)

    def test_resolve_commons_creative_license_non_match(self):
        spdx, note, regional_id = resolve_commons_creative_license("https://example.com/no/license")
        self.assertIsNone(spdx)
        self.assertIsNone(note)
        self.assertIsNone(regional_id)

    def test_resolve_commons_creative_license_all_flavors(self):
        cases = {
            "https://creativecommons.org/licenses/by-sa/3.0/": "CC-BY-SA-3.0",
            "https://creativecommons.org/licenses/by-nd/3.0/": "CC-BY-ND-3.0",
            "https://creativecommons.org/licenses/by-nc/4.0/": "CC-BY-NC-4.0",
            "https://creativecommons.org/licenses/by-nc-sa/4.0/": "CC-BY-NC-SA-4.0",
            "https://creativecommons.org/licenses/by-nc-nd/4.0/": "CC-BY-NC-ND-4.0",
        }
        for url, expected in cases.items():
            spdx, note, regional_id = resolve_commons_creative_license(url)
            self.assertEqual(spdx, expected)
            self.assertIsNone(note)
            self.assertIsNone(regional_id)

    def test_resolve_commons_creative_license_jp_variant(self):
        # New behavior: return base SPDX and a note when locale/jurisdiction variants encountered
        spdx, note, regional_id = resolve_commons_creative_license("https://creativecommons.org/licenses/by/2.1/jp/")
        # Current implementation maps to CC-BY-2.0 with a note
        self.assertEqual(spdx, "CC-BY-2.0")
        self.assertIsNotNone(note)
        # Be lenient about message contents
        self.assertIn("jp", note.lower())
        self.assertEqual(regional_id, "CC-BY-2.1-jp")

    # --- heuristic_spdx ---
    def test_heuristic_spdx_patterns(self):
        self.assertEqual(heuristic_spdx("https://opensource.org/licenses/MIT"), "MIT")
        self.assertEqual(heuristic_spdx("http://opensource.org/licenses/Apache-2.0"), "Apache-2.0")
        self.assertEqual(heuristic_spdx("https://opendatacommons.org/licenses/odbl/1.0/"), "ODbL-1.0")

    def test_heuristic_spdx_no_match(self):
        self.assertIsNone(heuristic_spdx("https://example.com/custom-license"))

    # --- fuzzy_ratio ---
    def test_fuzzy_ratio_similarity(self):
        a = "https://example.com/license/alpha"
        b = "https://example.com/license/alpha"  # identical
        self.assertAlmostEqual(fuzzy_ratio(a, b), 1.0, places=5)
        c = "https://example.com/license/beta"
        ratio = fuzzy_ratio(a, c)
        self.assertTrue(0 < ratio < 1)

    # --- resolve_fuzzy_match ---
    def _make_license(self, id_: str, url: str, name: str = None, type_: str = "standard") -> License:
        return License(id=id_, type=type_, name=name or id_, url=url)

    def test_resolve_fuzzy_match_no_session_or_host(self):
        self.assertEqual(resolve_fuzzy_match("x", "", "x", 0.8, None), [])

    def test_resolve_fuzzy_match_host_and_threshold(self):
        # Prepare licenses
        lic1 = self._make_license("MIT", "opensource.org/licenses/MIT", "MIT")
        lic2 = self._make_license("Apache-2.0", "opensource.org/licenses/Apache-2.0", "Apache")
        lic3 = self._make_license("ODbL-1.0", "opendatacommons.org/licenses/odbl/1.0/", "ODbL")
        # Only first two share the host 'opensource.org'
        self.session.scalars.return_value = [lic1, lic2, lic3]
        results = resolve_fuzzy_match(
            url_str="https://opensource.org/licenses/mit/",
            url_host="opensource.org",
            url_normalized="opensource.org/licenses/mit",
            fuzzy_threshold=0.6,
            db_session=self.session,
            max_candidates=2,
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(all(r.match_type == "fuzzy" for r in results))
        self.assertTrue(all(r.matched_catalog_url.startswith("opensource.org") for r in results))

    def test_resolve_fuzzy_match_applies_limit(self):
        lic_list = [self._make_license(f"L{i}", f"host.com/path{i}") for i in range(10)]
        self.session.scalars.return_value = lic_list
        results = resolve_fuzzy_match(
            url_str="host.com/path0",
            url_host="host.com",
            url_normalized="host.com/path0",
            fuzzy_threshold=0.0,  # accept all
            db_session=self.session,
            max_candidates=3,
        )
        self.assertEqual(len(results), 3)

    # --- resolve_license ---
    @patch("shared.common.license_utils.find_exact_match_license_url")
    def test_resolve_license_exact(self, mock_find):
        lic = self._make_license("MIT", "opensource.org/licenses/MIT", "MIT")
        mock_find.return_value = lic
        results = resolve_license("https://opensource.org/licenses/MIT", db_session=self.session)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].match_type, "exact")
        self.assertEqual(results[0].spdx_id, "MIT")

    @patch("shared.common.license_utils.find_exact_match_license_url", return_value=None)
    def test_resolve_license_creative_commons(self, _mock_find):
        # Provide session (implementation accesses db_session) but ensure exact path returns None
        results = resolve_license("https://creativecommons.org/licenses/by/4.0/", db_session=self.session)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].spdx_id, "CC-BY-4.0")
        self.assertEqual(results[0].match_type, "heuristic")

    @patch("shared.common.license_utils.find_exact_match_license_url", return_value=None)
    def test_resolve_license_spdx_catalog_url_db_hit(self, _mock_find):
        """SPDX catalog URLs (spdx.org/licenses/ID) should resolve via SPDX branch when license exists in DB."""
        spdx_url = "https://spdx.org/licenses/ODbL-1.0.html"
        lic = self._make_license("odbl-1.0", "https://spdx.org/licenses/ODbL-1.0.html", "ODbL 1.0")
        # Configure session to return our license when queried by ID
        self.session.query.return_value.filter.return_value.one_or_none.return_value = lic

        results = resolve_license(spdx_url, db_session=self.session)

        self.assertEqual(len(results), 1)
        r = results[0]
        # Implementation currently lowercases the SPDX ID extracted from the URL
        self.assertEqual(r.spdx_id, "odbl-1.0")
        self.assertEqual(r.license_id, "odbl-1.0")
        self.assertEqual(r.match_type, "heuristic")
        self.assertEqual(r.matched_source, "spdx-resolver")
        self.assertEqual(r.matched_name, "ODbL 1.0")
        self.assertEqual(r.matched_catalog_url, "https://spdx.org/licenses/ODbL-1.0.html")

    @patch("shared.common.license_utils.find_exact_match_license_url", return_value=None)
    def test_resolve_license_spdx_catalog_url_db_miss(self, _mock_find):
        """When SPDX ID is parsed from URL but not present in DB,
        resolver should log and return no SPDX-based result."""
        spdx_url = "https://spdx.org/licenses/ODbL-1.0.html"
        # Simulate no matching License in DB
        self.session.query.return_value.filter.return_value.one_or_none.return_value = None

        results = resolve_license(spdx_url, db_session=self.session)

        # Current behavior: we only log a warning and return an empty list when SPDX ID is not found in DB.
        self.assertEqual(results, [])

    @patch("shared.common.license_utils.find_exact_match_license_url", return_value=None)
    def test_resolve_license_generic_heuristic(self, _mock_find):
        # Provide URL that matches heuristic patterns
        results = resolve_license("https://choosealicense.com/licenses/mit/", db_session=self.session)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].spdx_id, "MIT")
        self.assertEqual(results[0].match_type, "heuristic")

    @patch("shared.common.license_utils.find_exact_match_license_url", return_value=None)
    def test_resolve_license_fuzzy(self, _mock_find):
        target_url = "https://licenses.example.org/pageA"
        licA = self._make_license("LIC-A", "licenses.example.org/pageA", "License A")
        licB = self._make_license("LIC-B", "licenses.example.org/pageB", "License B")
        self.session.scalars.return_value = [licA, licB]
        results = resolve_license(target_url, db_session=self.session, fuzzy_threshold=0.8)
        self.assertTrue(results)
        self.assertTrue(all(r.match_type == "fuzzy" for r in results))

    @patch("shared.common.license_utils.find_exact_match_license_url", return_value=None)
    def test_resolve_license_no_match(self, _mock_find):
        # Provide unique host; no fuzzy allowed; should be empty
        results = resolve_license(
            "https://unknown.example.xyz/some/path",
            db_session=self.session,
            allow_fuzzy=False,
        )
        self.assertEqual(results, [])

    # --- find_exact_match_license_url ---
    def test_find_exact_match_license_url_hit(self):
        expected_license = self._make_license("MIT", "opensource.org/licenses/MIT", "MIT")
        self.session.query.return_value.filter.return_value.first.return_value = expected_license
        result = find_exact_match_license_url("opensource.org/licenses/MIT", self.session)
        self.assertIs(result, expected_license)

    def test_find_exact_match_license_url_miss(self):
        self.session.query.return_value.filter.return_value.first.return_value = None
        result = find_exact_match_license_url("opensource.org/licenses/Apache-2.0", self.session)
        self.assertIsNone(result)

    # --- MatchingLicense dataclass simple instantiation ---
    def test_matching_license_dataclass(self):
        ml = MatchingLicense(
            license_id="L1",
            license_url="http://x.com/L1",
            normalized_url="x.com/L1",
            match_type="exact",
            confidence=1.0,
            spdx_id="L1",
            matched_name="Name",
            matched_catalog_url="x.com/L1",
            matched_source="db.license",
        )
        self.assertEqual(ml.license_id, "L1")
        self.assertEqual(ml.match_type, "exact")
        self.assertEqual(ml.confidence, 1.0)


class TestAssignLicenseByUrl(unittest.TestCase):
    """Unit tests for assign_license_by_url."""

    def _make_match(self, license_id="MIT", match_type="exact", confidence=1.0):
        return MatchingLicense(
            license_id=license_id,
            license_url="http://example.com/license",
            normalized_url="example.com/license",
            match_type=match_type,
            confidence=confidence,
            matched_name="MIT License",
            matched_catalog_url="http://example.com/license",
            matched_source="db.license",
        )

    def _make_feed(self, license_url="http://example.com/license", license_id=None):
        feed = MagicMock()
        feed.stable_id = "test-feed-1"
        feed.id = "feed-id-1"
        feed.license_url = license_url
        feed.license_id = license_id
        feed.license_notes = None
        feed.feed_license_changes = []
        return feed

    # --- No license_url ---

    def test_no_license_url_returns_none(self):
        feed = self._make_feed(license_url=None)
        result = assign_license_by_url(feed, MagicMock())
        self.assertIsNone(result)
        self.assertIsNone(feed.license_id)

    def test_empty_license_url_returns_none(self):
        feed = self._make_feed(license_url="")
        result = assign_license_by_url(feed, MagicMock())
        self.assertIsNone(result)

    # --- No match ---

    @patch("shared.common.license_utils.resolve_license")
    def test_no_match_returns_none(self, mock_resolve):
        mock_resolve.return_value = []
        feed = self._make_feed()
        result = assign_license_by_url(feed, MagicMock())
        self.assertIsNone(result)
        self.assertIsNone(feed.license_id)
        self.assertEqual(feed.feed_license_changes, [])

    # --- Multiple matches ---

    @patch("shared.common.license_utils.resolve_license")
    def test_multiple_matches_skips_assignment(self, mock_resolve):
        mock_resolve.return_value = [
            self._make_match("MIT", "fuzzy", 0.96),
            self._make_match("Apache-2.0", "fuzzy", 0.94),
        ]
        feed = self._make_feed()
        result = assign_license_by_url(feed, MagicMock())
        self.assertIsNone(result)
        self.assertIsNone(feed.license_id)
        self.assertEqual(feed.feed_license_changes, [])

    # --- Single exact match — auto-verified ---

    @patch("shared.common.license_utils.resolve_license")
    def test_exact_match_assigns_and_marks_verified(self, mock_resolve):
        match = self._make_match("MIT", "exact", 1.0)
        mock_resolve.return_value = [match]
        feed = self._make_feed()

        result = assign_license_by_url(feed, MagicMock())

        self.assertEqual(result, match)
        self.assertEqual(feed.license_id, "MIT")
        self.assertEqual(len(feed.feed_license_changes), 1)
        self.assertTrue(feed.feed_license_changes[0].verified)

    @patch("shared.common.license_utils.resolve_license")
    def test_heuristic_high_confidence_assigns_and_marks_verified(self, mock_resolve):
        match = self._make_match("CC-BY-4.0", "heuristic", 0.99)
        mock_resolve.return_value = [match]
        feed = self._make_feed()

        result = assign_license_by_url(feed, MagicMock())

        self.assertEqual(result, match)
        self.assertEqual(feed.license_id, "CC-BY-4.0")
        self.assertTrue(feed.feed_license_changes[0].verified)

    @patch("shared.common.license_utils.resolve_license")
    def test_threshold_boundary_095_marks_verified(self, mock_resolve):
        match = self._make_match("ODbL-1.0", "heuristic", 0.95)
        mock_resolve.return_value = [match]
        feed = self._make_feed()

        assign_license_by_url(feed, MagicMock())

        self.assertTrue(feed.feed_license_changes[0].verified)

    # --- Fuzzy / low-confidence match — unverified ---

    @patch("shared.common.license_utils.resolve_license")
    def test_fuzzy_match_assigns_but_unverified(self, mock_resolve):
        match = self._make_match("MIT", "fuzzy", 0.94)
        mock_resolve.return_value = [match]
        feed = self._make_feed()

        result = assign_license_by_url(feed, MagicMock())

        self.assertEqual(result, match)
        self.assertEqual(feed.license_id, "MIT")
        self.assertFalse(feed.feed_license_changes[0].verified)

    @patch("shared.common.license_utils.resolve_license")
    def test_below_threshold_unverified(self, mock_resolve):
        match = self._make_match("MIT", "heuristic", 0.80)
        mock_resolve.return_value = [match]
        feed = self._make_feed()

        assign_license_by_url(feed, MagicMock())

        self.assertFalse(feed.feed_license_changes[0].verified)

    # --- Duplicate assignment guard ---

    @patch("shared.common.license_utils.resolve_license")
    def test_same_license_id_no_new_audit_row(self, mock_resolve):
        match = self._make_match("MIT", "exact", 1.0)
        mock_resolve.return_value = [match]
        feed = self._make_feed(license_id="MIT")  # already assigned

        result = assign_license_by_url(feed, MagicMock())

        self.assertEqual(result, match)
        self.assertEqual(feed.license_id, "MIT")
        self.assertEqual(feed.feed_license_changes, [])  # no new audit row

    # --- only_if_single=False allows multiple matches ---

    @patch("shared.common.license_utils.resolve_license")
    def test_only_if_single_false_assigns_best_match(self, mock_resolve):
        best = self._make_match("MIT", "fuzzy", 0.97)
        second = self._make_match("Apache-2.0", "fuzzy", 0.94)
        mock_resolve.return_value = [best, second]
        feed = self._make_feed()

        result = assign_license_by_url(feed, MagicMock(), only_if_single=False)

        self.assertEqual(result, best)
        self.assertEqual(feed.license_id, "MIT")
