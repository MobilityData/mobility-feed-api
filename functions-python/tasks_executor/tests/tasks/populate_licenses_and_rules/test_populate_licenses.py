import unittest
from unittest.mock import MagicMock, patch

import requests

from shared.database_gen.sqlacodegen_models import Licensetag, Rule
from tasks.licenses.populate_licenses import (
    LICENSES_API_URL,
    populate_licenses_task,
)

# Mock data for GitHub API responses
MOCK_LICENSE_LIST = [
    {
        "name": "MIT.json",
        "type": "file",
        "download_url": "http://mockurl/MIT.json",
    },
    {
        "name": "BSD-3-Clause.json",
        "type": "file",
        "download_url": "http://mockurl/BSD-3-Clause.json",
    },
    {
        "name": "no-spdx.json",
        "type": "file",
        "download_url": "http://mockurl/no-spdx.json",
    },
    {
        "name": "README.md",
        "type": "file",
        "download_url": "http://mockurl/README.md",
    },
]

MOCK_LICENSE_MIT = {
    "spdx": {
        "licenseId": "MIT",
        "name": "MIT License",
        "crossRef": [{"url": "https://opensource.org/licenses/MIT"}],
        "licenseText": "MIT License text...",
        "licenseTextHtml": "<p>MIT License text...</p>",
    },
    "permissions": ["commercial-use", "distribution"],
    "conditions": ["include-copyright"],
    "limitations": [],
    "tags": ["spdx:osi-approved", "license:open-source"],
}

MOCK_LICENSE_BSD = {
    "spdx": {
        "licenseId": "BSD-3-Clause",
        "name": "BSD 3-Clause License",
        "crossRef": [{"url": "https://opensource.org/licenses/BSD-3-Clause"}],
        "licenseText": "BSD license text...",
        "licenseTextHtml": "<p>BSD license text...</p>",
    },
    "permissions": ["commercial-use"],
    "conditions": [],
    "limitations": ["liability", "warranty"],
    "tags": [],
}

MOCK_LICENSE_NO_SPDX = {"licenseId": "NO-SPDX-ID", "name": "No SPDX License"}


class TestPopulateLicenses(unittest.TestCase):
    def _mock_requests_get(self, mock_get):
        """Helper to configure mock for requests.get."""
        mock_responses = {
            LICENSES_API_URL: MagicMock(json=lambda: MOCK_LICENSE_LIST),
            "http://mockurl/MIT.json": MagicMock(json=lambda: MOCK_LICENSE_MIT),
            "http://mockurl/BSD-3-Clause.json": MagicMock(
                json=lambda: MOCK_LICENSE_BSD
            ),
            "http://mockurl/no-spdx.json": MagicMock(json=lambda: MOCK_LICENSE_NO_SPDX),
        }

        def get_side_effect(url, timeout=None):
            if url in mock_responses:
                response = mock_responses[url]
                response.raise_for_status.return_value = None
                return response
            raise requests.exceptions.RequestException(f"URL not mocked: {url}")

        mock_get.side_effect = get_side_effect

    @staticmethod
    def _make_filter_mock(lookup):
        """Return a mock filter that resolves IDs/names from the given lookup dict."""

        def filter_side_effect(cond):
            keys = cond.right.value
            mock_filter = MagicMock()
            mock_filter.all.return_value = [lookup[k] for k in keys if k in lookup]
            return mock_filter

        return filter_side_effect

    @patch("tasks.licenses.populate_licenses.requests.get")
    def test_populate_licenses_success(self, mock_get):
        """Test successful population of licenses including tag assignment."""
        # Arrange
        self._mock_requests_get(mock_get)
        mock_db_session = MagicMock()
        mock_db_session.get.return_value = None  # Simulate no existing licenses

        all_mock_rules = {
            "commercial-use": Rule(name="commercial-use"),
            "distribution": Rule(name="distribution"),
            "include-copyright": Rule(name="include-copyright"),
            "liability": Rule(name="liability"),
            "warranty": Rule(name="warranty"),
        }
        all_mock_tags = {
            "spdx:osi-approved": Licensetag(id="spdx:osi-approved"),
            "license:open-source": Licensetag(id="license:open-source"),
        }

        rule_filter = self._make_filter_mock(all_mock_rules)
        tag_filter = self._make_filter_mock(all_mock_tags)

        def query_side_effect(model_class):
            """Return a different mock chain depending on the queried model."""
            mock_query = MagicMock()
            if model_class is Rule:
                mock_query.filter.side_effect = rule_filter
            elif model_class is Licensetag:
                mock_query.filter.side_effect = tag_filter
            return mock_query

        mock_db_session.query.side_effect = query_side_effect

        # Act
        populate_licenses_task(dry_run=False, db_session=mock_db_session)

        # Assert: two SPDX licenses added (no merge for new records)
        self.assertEqual(mock_db_session.add.call_count, 2)
        mock_db_session.merge.assert_not_called()
        mock_db_session.rollback.assert_not_called()

        # Inspect the License objects added
        added_licenses = [call.args[0] for call in mock_db_session.add.call_args_list]
        mit_license = next(
            (lic for lic in added_licenses if getattr(lic, "id", None) == "MIT"), None
        )
        self.assertIsNotNone(mit_license)
        self.assertEqual(getattr(mit_license, "name", None), "MIT License")
        self.assertTrue(getattr(mit_license, "is_spdx", False))
        self.assertEqual(len(getattr(mit_license, "rules", [])), 3)
        # MIT license has 2 tags in mock data
        self.assertEqual(len(getattr(mit_license, "licensetags", [])), 2)

    @patch("tasks.licenses.populate_licenses.requests.get")
    def test_populate_licenses_dry_run(self, mock_get):
        """Test that no database changes are made during a dry run."""
        # Arrange
        self._mock_requests_get(mock_get)
        mock_db_session = MagicMock()

        # Act
        populate_licenses_task(dry_run=True, db_session=mock_db_session)

        # Assert
        mock_db_session.get.assert_not_called()
        mock_db_session.merge.assert_not_called()
        mock_db_session.rollback.assert_not_called()

    @patch("tasks.licenses.populate_licenses.requests.get")
    def test_request_exception_handling(self, mock_get):
        """Test handling of a requests exception."""
        # Arrange
        mock_get.side_effect = requests.exceptions.RequestException("Network Error")
        mock_db_session = MagicMock()

        # Act & Assert
        with self.assertRaises(requests.exceptions.RequestException):
            populate_licenses_task(dry_run=False, db_session=mock_db_session)

        mock_db_session.merge.assert_not_called()
        # Rollback is not called because the exception happens before the db try/except block
        mock_db_session.rollback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
