#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import unittest
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Feed
from shared.helpers.gtfs_validator_common import GTFS_VALIDATOR_URL_STAGING
from shared.helpers.tests.test_shared.test_utils.database_utils import default_db_url
from tasks.validation_reports.rebuild_missing_validation_reports import (
    rebuild_missing_validation_reports_handler,
    get_parameters,
    rebuild_missing_validation_reports,
)


class TestTasksExecutor(unittest.TestCase):
    def test_get_parameters(self):
        """
        Test the get_parameters function to ensure it correctly extracts parameters from the payload.
        """
        payload = {
            "dry_run": True,
            "filter_after_in_days": 14,
            "filter_statuses": ["status1", "status2"],
        }

        (
            dry_run,
            filter_after_in_days,
            filter_statuses,
            prod_env,
            validator_endpoint,
        ) = get_parameters(payload)

        self.assertTrue(dry_run)
        self.assertEqual(filter_after_in_days, 14)
        self.assertEqual(filter_statuses, ["status1", "status2"])
        self.assertFalse(prod_env)
        self.assertEqual(validator_endpoint, GTFS_VALIDATOR_URL_STAGING)

    @patch(
        "tasks.validation_reports.rebuild_missing_validation_reports.rebuild_missing_validation_reports"
    )
    def test_rebuild_missing_validation_reports_entry(
        self, rebuild_missing_validation_reports_mock
    ):
        """
        Test the rebuild_missing_validation_reports_entry function.
        Assert that it correctly calls the rebuild_missing_validation_reports function with the expected parameters.
        """
        # Mock payload for the test
        payload = {
            "dry_run": True,
            "filter_after_in_days": 14,
            "filter_statuses": ["status1", "status2"],
        }
        expected_response = MagicMock()
        rebuild_missing_validation_reports_mock.return_value = expected_response
        response = rebuild_missing_validation_reports_handler(payload)

        self.assertEqual(response, expected_response)
        rebuild_missing_validation_reports_mock.assert_called_once_with(
            validator_endpoint=GTFS_VALIDATOR_URL_STAGING,
            dry_run=True,
            filter_after_in_days=14,
            filter_statuses=["status1", "status2"],
            prod_env=False,
        )

    @with_db_session(db_url=default_db_url)
    @patch(
        "tasks.validation_reports.rebuild_missing_validation_reports.execute_workflows",
    )
    @patch(
        "tasks.validation_reports.rebuild_missing_validation_reports.QUERY_LIMIT", 10
    )
    def test_rebuild_missing_validation_reports_one_page(
        self, execute_workflows_mock, db_session: Session
    ):
        """
        Test the rebuild_missing_validation_reports function with a single page of results.
        We are assuming tha the dataset has 7 datasets, and the query limit is set to 10.
        """
        execute_workflows_mock.return_value = []
        response = rebuild_missing_validation_reports(
            db_session=db_session,
            validator_endpoint="https://i_dont.exists.com",
            dry_run=False,
            prod_env=False,
        )

        # Assert the expected behavior
        self.assertIsNotNone(response)
        self.assertEquals(response["total_processed"], 9)
        self.assertEquals(
            response["message"],
            "Rebuild missing validation reports task executed successfully.",
        )
        execute_workflows_mock.assert_called_once()

    @with_db_session(db_url=default_db_url)
    @patch(
        "tasks.validation_reports.rebuild_missing_validation_reports.execute_workflows",
    )
    @patch("tasks.validation_reports.rebuild_missing_validation_reports.QUERY_LIMIT", 2)
    def test_rebuild_missing_validation_reports_two_pages(
        self, execute_workflows_mock, db_session: Session
    ):
        """
        Test the rebuild_missing_validation_reports function with a single page of results.
        We are assuming tha the dataset has 7 datasets, and the query limit is set to 2.
        """
        execute_workflows_mock.return_value = []
        response = rebuild_missing_validation_reports(
            db_session=db_session,
            validator_endpoint="https://i_dont.exists.com",
            dry_run=False,
            prod_env=False,
        )

        # Assert the expected behavior
        self.assertIsNotNone(response)
        self.assertEquals(response["total_processed"], 9)
        self.assertEquals(
            response["message"],
            "Rebuild missing validation reports task executed successfully.",
        )
        self.assertEquals(execute_workflows_mock.call_count, 5)

    @with_db_session(db_url=default_db_url)
    @patch(
        "tasks.validation_reports.rebuild_missing_validation_reports.execute_workflows",
    )
    @patch("tasks.validation_reports.rebuild_missing_validation_reports.QUERY_LIMIT", 2)
    def test_rebuild_missing_validation_reports_dryrun(
        self, execute_workflows_mock, db_session: Session
    ):
        """
        Test the rebuild_missing_validation_reports function with a single page of results.
        We are assuming tha the dataset has 7 datasets, and the query limit is set to 2.
        """
        execute_workflows_mock.return_value = []
        response = rebuild_missing_validation_reports(
            db_session=db_session,
            validator_endpoint="https://i_dont.exists.com",
            dry_run=True,
            prod_env=False,
        )

        # Assert the expected behavior
        self.assertIsNotNone(response)
        self.assertEquals(response["total_processed"], 9)
        self.assertEquals(response["message"], "Dry run: no datasets processed.")
        execute_workflows_mock.assert_not_called()

    @with_db_session(db_url=default_db_url)
    @patch(
        "tasks.validation_reports.rebuild_missing_validation_reports.execute_workflows",
    )
    @patch(
        "tasks.validation_reports.rebuild_missing_validation_reports.QUERY_LIMIT", 10
    )
    def test_rebuild_missing_validation_reports_filter_active(
        self, execute_workflows_mock, db_session: Session
    ):
        """
        Test the rebuild_missing_validation_reports function with a single page of results.
        We are assuming tha the dataset has 7 datasets, and the query limit is set to 2.
        """
        active_counter = (
            db_session.query(Gtfsdataset)
            .join(Gtfsdataset.feed)
            .filter(Feed.status == "active")
            .count()
        )
        execute_workflows_mock.return_value = []
        response = rebuild_missing_validation_reports(
            db_session=db_session,
            validator_endpoint="https://i_dont.exists.com",
            dry_run=False,
            prod_env=False,
            filter_statuses=["active"],
        )

        # Assert the expected behavior
        self.assertIsNotNone(response)
        self.assertEquals(response["total_processed"], active_counter)
        self.assertEquals(
            response["message"],
            "Rebuild missing validation reports task executed successfully.",
        )
        self.assertEquals(execute_workflows_mock.call_count, 1)

    @with_db_session(db_url=default_db_url)
    @patch(
        "tasks.validation_reports.rebuild_missing_validation_reports.execute_workflows",
    )
    @patch(
        "tasks.validation_reports.rebuild_missing_validation_reports.QUERY_LIMIT", 10
    )
    def test_rebuild_missing_validation_reports_filter_no_results(
        self, execute_workflows_mock, db_session: Session
    ):
        """
        Test the rebuild_missing_validation_reports function with a single page of results.
        We are assuming tha the dataset has 7 datasets, and the query limit is set to 2.
        """
        execute_workflows_mock.return_value = []
        response = rebuild_missing_validation_reports(
            db_session=db_session,
            validator_endpoint="https://i_dont.exists.com",
            dry_run=False,
            prod_env=False,
            filter_statuses=["future"],
        )

        # Assert the expected behavior
        self.assertIsNotNone(response)
        self.assertEquals(response["total_processed"], 0)
        self.assertEquals(
            response["message"],
            "Rebuild missing validation reports task executed successfully.",
        )
        execute_workflows_mock.assert_not_called()
