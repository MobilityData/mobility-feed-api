import unittest
from unittest.mock import MagicMock, patch

import requests
from sqlalchemy.exc import SQLAlchemyError

from shared.database_gen.sqlacodegen_models import Rule
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

    @patch("tasks.licenses.populate_licenses.requests.get")
    def test_populate_licenses_success(self, mock_get):
        """Test successful population of licenses."""
        # Arrange
        self._mock_requests_get(mock_get)
        mock_db_session = MagicMock()
        mock_db_session.get.return_value = None  # Simulate no existing licenses

        # Mock the rules query
        mock_rules = [
            Rule(name="commercial-use"),
            Rule(name="distribution"),
            Rule(name="include-copyright"),
            Rule(name="liability"),
            Rule(name="warranty"),
        ]
        mock_db_session.query.return_value.filter.return_value.all.return_value = (
            mock_rules
        )

        # Act
        populate_licenses_task(dry_run=False, db_session=mock_db_session)

        # Assert
        self.assertEqual(mock_db_session.merge.call_count, 2)
        mock_db_session.rollback.assert_not_called()

        # Check that merge was called with correctly constructed License objects
        call_args_list = mock_db_session.merge.call_args_list
        merged_licenses = [arg.args[0] for arg in call_args_list]

        mit_license = next((lic for lic in merged_licenses if lic.id == "MIT"), None)
        self.assertIsNotNone(mit_license)
        self.assertEqual(mit_license.name, "MIT License")
        self.assertTrue(mit_license.is_spdx)
        self.assertEqual(len(mit_license.rules), 3)

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

    @patch("tasks.licenses.populate_licenses.requests.get")
    def test_database_exception_handling(self, mock_get):
        """Test handling of a database exception during merge."""
        # Arrange
        self._mock_requests_get(mock_get)
        mock_db_session = MagicMock()
        mock_db_session.get.return_value = None
        mock_db_session.merge.side_effect = SQLAlchemyError("DB connection failed")

        # Act & Assert
        with self.assertRaises(SQLAlchemyError):
            populate_licenses_task(dry_run=False, db_session=mock_db_session)

        self.assertTrue(mock_db_session.merge.called)
        mock_db_session.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
