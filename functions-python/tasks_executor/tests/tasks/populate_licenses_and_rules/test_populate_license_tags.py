import unittest
from unittest.mock import patch, MagicMock
import requests
from sqlalchemy.exc import SQLAlchemyError

from tasks.licenses.populate_license_tags import (
    populate_license_tags,
    TAGS_JSON_URL,
)
from shared.database_gen.sqlacodegen_models import LicenseTag, LicenseTagGroup


class TestPopulateLicenseTags(unittest.TestCase):
    def setUp(self):
        """Set up mock tags JSON data for tests."""
        self.mock_tags_json = {
            "spdx": {
                "_group": {
                    "short": "SPDX status",
                    "description": "Metadata from the SPDX list.",
                },
                "osi-approved": {
                    "description": "Approved by the Open Source Initiative.",
                    "url": "https://opensource.org/licenses",
                },
                "fsf-free": {
                    "description": "Classified as free by the FSF.",
                    "url": "https://www.gnu.org/licenses/license-list.html",
                },
            },
            "license": {
                "_group": {
                    "short": "License type",
                    "description": "High-level license family classification.",
                },
                "open-source": {
                    "description": "Standard open-source software licenses.",
                    "url": "https://opensource.org/licenses",
                },
            },
        }

    @patch("tasks.licenses.populate_license_tags.requests.get")
    def test_populate_tags_success(self, mock_requests_get):
        """Test successful population of license tags."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_tags_json
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        mock_db_session = MagicMock()

        # Act
        populate_license_tags(dry_run=False, db_session=mock_db_session)

        # Assert: 2 groups ("spdx", "license") + 3 tags = 5 total merges
        mock_requests_get.assert_called_once_with(TAGS_JSON_URL, timeout=10)
        self.assertEqual(mock_db_session.merge.call_count, 5)

        call_args_list = mock_db_session.merge.call_args_list

        # First two merges should be groups (order: "spdx", then "license")
        group1 = call_args_list[0].args[0]
        self.assertIsInstance(group1, LicenseTagGroup)
        self.assertEqual(group1.id, "spdx")
        self.assertEqual(group1.short_name, "SPDX status")
        self.assertEqual(group1.description, "Metadata from the SPDX list.")

        group2 = call_args_list[1].args[0]
        self.assertIsInstance(group2, LicenseTagGroup)
        self.assertEqual(group2.id, "license")
        self.assertEqual(group2.short_name, "License type")
        self.assertEqual(
            group2.description, "High-level license family classification."
        )

        # Remaining three merges are tags; verify IDs, groups, tags and URLs
        tag1 = call_args_list[2].args[0]
        self.assertIsInstance(tag1, LicenseTag)
        self.assertEqual(tag1.id, "spdx:osi-approved")
        self.assertEqual(tag1.group, "spdx")
        self.assertEqual(tag1.tag, "osi-approved")
        self.assertEqual(tag1.description, "Approved by the Open Source Initiative.")
        self.assertEqual(tag1.url, "https://opensource.org/licenses")

        tag2 = call_args_list[3].args[0]
        self.assertIsInstance(tag2, LicenseTag)
        self.assertEqual(tag2.id, "spdx:fsf-free")
        self.assertEqual(tag2.group, "spdx")
        self.assertEqual(tag2.tag, "fsf-free")
        self.assertEqual(tag2.url, "https://www.gnu.org/licenses/license-list.html")

        tag3 = call_args_list[4].args[0]
        self.assertIsInstance(tag3, LicenseTag)
        self.assertEqual(tag3.id, "license:open-source")
        self.assertEqual(tag3.group, "license")
        self.assertEqual(tag3.tag, "open-source")
        self.assertEqual(tag3.url, "https://opensource.org/licenses")

        mock_db_session.rollback.assert_not_called()

    @patch("tasks.licenses.populate_license_tags.requests.get")
    def test_populate_tags_dry_run(self, mock_requests_get):
        """Test that no database changes are made during a dry run."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_tags_json
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        mock_db_session = MagicMock()

        # Act
        populate_license_tags(dry_run=True, db_session=mock_db_session)

        # Assert
        mock_requests_get.assert_called_once_with(TAGS_JSON_URL, timeout=10)
        mock_db_session.merge.assert_not_called()
        mock_db_session.rollback.assert_not_called()

    @patch("tasks.licenses.populate_license_tags.requests.get")
    def test_request_exception_handling(self, mock_requests_get):
        """Test handling of a network exception."""
        # Arrange
        mock_requests_get.side_effect = requests.exceptions.RequestException(
            "Network Error"
        )
        mock_db_session = MagicMock()

        # Act & Assert
        with self.assertRaises(requests.exceptions.RequestException):
            populate_license_tags(dry_run=False, db_session=mock_db_session)

        mock_db_session.merge.assert_not_called()
        mock_db_session.rollback.assert_not_called()

    @patch("tasks.licenses.populate_license_tags.requests.get")
    def test_database_exception_handling(self, mock_requests_get):
        """Test handling of a database exception during merge."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_tags_json
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        mock_db_session = MagicMock()
        mock_db_session.merge.side_effect = SQLAlchemyError("DB connection failed")

        # Act & Assert
        with self.assertRaises(SQLAlchemyError):
            populate_license_tags(dry_run=False, db_session=mock_db_session)

        self.assertTrue(mock_db_session.merge.called)
        mock_db_session.rollback.assert_called_once()

    @patch("tasks.licenses.populate_license_tags.requests.get")
    def test_group_metadata_skipped(self, mock_requests_get):
        """Test that _group metadata entries become groups but not tags."""
        # Arrange – only one group with only the _group metadata key
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "spdx": {
                "_group": {
                    "short": "SPDX status",
                    "description": "Metadata.",
                }
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        mock_db_session = MagicMock()

        # Act
        populate_license_tags(dry_run=False, db_session=mock_db_session)

        # Assert: only a group is created; no tags
        mock_db_session.merge.assert_called_once()
        group_obj = mock_db_session.merge.call_args.args[0]
        self.assertIsInstance(group_obj, LicenseTagGroup)
        self.assertEqual(group_obj.id, "spdx")


if __name__ == "__main__":
    unittest.main()
