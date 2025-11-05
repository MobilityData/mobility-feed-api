import logging
import unittest
from unittest.mock import MagicMock, call, patch

import pytest
import requests
from shared.database.database import Session
from shared.database_gen.sqlacodegen_models import License, Rule
from tasks.licenses.populate_licenses import populate_licenses_task

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
    def setUp(self):
        # Create an in-memory SQLite database for testing
        self.session = Session(bind=self.engine)

    def tearDown(self):
        self.session.close()

    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine

        from shared.database_gen.sqlacodegen_models import Base

        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(cls.engine)

    @classmethod
    def tearDownClass(cls):
        from shared.database_gen.sqlacodegen_models import Base

        Base.metadata.drop_all(cls.engine)

    def _mock_requests_get(self, mock_get):
        """Helper to configure mock for requests.get."""
        mock_responses = {
            "https://api.github.com/repos/MobilityData/licenses-aas/contents/data/licenses": MagicMock(
                json=lambda: MOCK_LICENSE_LIST
            ),
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
        self._mock_requests_get(mock_get)

        # Pre-populate rules
        rules_to_add = [
            Rule(id="commercial-use", name="commercial-use", type="permission"),
            Rule(id="distribution", name="distribution", type="permission"),
            Rule(id="include-copyright", name="include-copyright", type="condition"),
            Rule(id="liability", name="liability", type="limitation"),
            Rule(id="warranty", name="warranty", type="limitation"),
        ]
        self.session.add_all(rules_to_add)
        self.session.commit()

        populate_licenses_task(dry_run=False, db_session=self.session)

        licenses = self.session.query(License).order_by(License.id).all()
        self.assertEqual(len(licenses), 2)

        # Check MIT License
        mit_license = licenses[1]
        self.assertEqual(mit_license.id, "MIT")
        self.assertEqual(mit_license.name, "MIT License")
        self.assertTrue(mit_license.is_spdx)
        self.assertEqual(len(mit_license.rules), 3)
        rule_names = sorted([rule.name for rule in mit_license.rules])
        self.assertEqual(
            rule_names, ["commercial-use", "distribution", "include-copyright"]
        )

        # Check BSD License
        bsd_license = licenses[0]
        self.assertEqual(bsd_license.id, "BSD-3-Clause")
        self.assertEqual(bsd_license.name, "BSD 3-Clause License")
        self.assertEqual(len(bsd_license.rules), 3)
        rule_names = sorted([rule.name for rule in bsd_license.rules])
        self.assertEqual(rule_names, ["commercial-use", "liability", "warranty"])

    @patch("tasks.licenses.populate_licenses.requests.get")
    def test_populate_licenses_dry_run(self, mock_get):
        self._mock_requests_get(mock_get)

        with self.assertLogs("tasks.licenses.populate_licenses", level="INFO") as cm:
            populate_licenses_task(dry_run=True, db_session=self.session)
            self.assertIn(
                "INFO:tasks.licenses.populate_licenses:Dry run: would process 2 licenses.",
                cm.output,
            )

        licenses_count = self.session.query(License).count()
        self.assertEqual(licenses_count, 0)

    @patch("tasks.licenses.populate_licenses.requests.get")
    def test_populate_licenses_request_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Network Error")

        with self.assertRaises(requests.exceptions.RequestException):
            populate_licenses_task(dry_run=False, db_session=self.session)

    @patch("tasks.licenses.populate_licenses.requests.get")
    def test_update_existing_license(self, mock_get):
        self._mock_requests_get(mock_get)

        # Pre-populate license and a rule
        existing_license = License(
            id="MIT", name="Old MIT Name", url="http://oldurl.com"
        )
        existing_rule = Rule(id="private-use", name="private-use", type="permission")
        existing_license.rules.append(existing_rule)
        self.session.add(existing_license)
        self.session.commit()

        # Run the task to update
        populate_licenses_task(dry_run=False, db_session=self.session)

        updated_license = self.session.query(License).filter_by(id="MIT").one()
        self.assertEqual(updated_license.name, "MIT License")
        self.assertEqual(updated_license.url, "https://opensource.org/licenses/MIT")
        # Check that rules are updated, not appended
        self.assertNotEqual(len(updated_license.rules), 4)


if __name__ == "__main__":
    unittest.main()
