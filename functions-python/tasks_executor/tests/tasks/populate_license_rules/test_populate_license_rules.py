import unittest
from unittest.mock import patch, MagicMock
import requests
from sqlalchemy.exc import SQLAlchemyError

from tasks.licenses.populate_license_rules import (
    populate_license_rules_task,
    RULES_JSON_URL,
)
from shared.database_gen.sqlacodegen_models import Rule


class TestPopulateLicenseRules(unittest.TestCase):
    def setUp(self):
        """Set up mock data for tests."""
        self.mock_rules_json = {
            "permissions": [
                {
                    "name": "commercial-use",
                    "label": "Commercial Use",
                    "description": "The licensed material may be used for commercial purposes.",
                }
            ],
            "conditions": [
                {
                    "name": "include-copyright",
                    "label": "Include Copyright",
                    "description": "A copy of the copyright and license notices must be included.",
                }
            ],
            "limitations": [],
        }

    @patch("tasks.licenses.populate_license_rules.requests.get")
    def test_populate_rules_success(self, mock_requests_get):
        """Test successful population of license rules."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_rules_json
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        mock_db_session = MagicMock()

        # Act
        populate_license_rules_task(dry_run=False, db_session=mock_db_session)

        # Assert
        mock_requests_get.assert_called_once_with(RULES_JSON_URL, timeout=10)
        self.assertEqual(mock_db_session.merge.call_count, 2)

        # Check that merge was called with correctly constructed Rule objects
        call_args_list = mock_db_session.merge.call_args_list

        # Check first call
        arg1 = call_args_list[0].args[0]
        self.assertIsInstance(arg1, Rule)
        self.assertEqual(arg1.name, "commercial-use")
        self.assertEqual(arg1.type, "permission")

        # Check second call
        arg2 = call_args_list[1].args[0]
        self.assertIsInstance(arg2, Rule)
        self.assertEqual(arg2.name, "include-copyright")
        self.assertEqual(arg2.type, "condition")

        mock_db_session.rollback.assert_not_called()

    @patch("tasks.licenses.populate_license_rules.requests.get")
    def test_populate_rules_dry_run(self, mock_requests_get):
        """Test that no database changes are made during a dry run."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_rules_json
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        mock_db_session = MagicMock()

        # Act
        populate_license_rules_task(dry_run=True, db_session=mock_db_session)

        # Assert
        mock_requests_get.assert_called_once_with(RULES_JSON_URL, timeout=10)
        mock_db_session.merge.assert_not_called()
        mock_db_session.rollback.assert_not_called()

    @patch("tasks.licenses.populate_license_rules.requests.get")
    def test_request_exception_handling(self, mock_requests_get):
        """Test handling of a requests exception."""
        # Arrange
        mock_requests_get.side_effect = requests.exceptions.RequestException(
            "Network Error"
        )
        mock_db_session = MagicMock()

        # Act & Assert
        with self.assertRaises(requests.exceptions.RequestException):
            populate_license_rules_task(dry_run=False, db_session=mock_db_session)

        mock_db_session.merge.assert_not_called()
        mock_db_session.rollback.assert_not_called()

    @patch("tasks.licenses.populate_license_rules.requests.get")
    def test_database_exception_handling(self, mock_requests_get):
        """Test handling of a database exception during merge."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_rules_json
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        mock_db_session = MagicMock()
        mock_db_session.merge.side_effect = SQLAlchemyError("DB connection failed")

        # Act & Assert
        with self.assertRaises(SQLAlchemyError):
            populate_license_rules_task(dry_run=False, db_session=mock_db_session)

        self.assertTrue(mock_db_session.merge.called)
        mock_db_session.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
