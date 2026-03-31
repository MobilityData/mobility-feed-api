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
from unittest.mock import patch, MagicMock, call

from shared.helpers.gtfs_validator_common import GTFS_VALIDATOR_URL_STAGING
from tasks.validation_reports.rebuild_missing_validation_reports import (
    rebuild_missing_validation_reports_handler,
    get_parameters,
    rebuild_missing_validation_reports,
)

_MODULE = "tasks.validation_reports.rebuild_missing_validation_reports"


class TestGetParameters(unittest.TestCase):
    def test_defaults(self):
        dry_run, filter_after_in_days, filter_statuses, prod_env, validator_endpoint, force_update, limit = get_parameters({})
        self.assertTrue(dry_run)
        self.assertEqual(filter_after_in_days, 7)
        self.assertIsNone(filter_statuses)
        self.assertFalse(prod_env)
        self.assertEqual(validator_endpoint, GTFS_VALIDATOR_URL_STAGING)
        self.assertFalse(force_update)
        self.assertIsNone(limit)

    def test_all_params(self):
        payload = {
            "dry_run": False,
            "filter_after_in_days": 30,
            "filter_statuses": ["active"],
            "validator_endpoint": "https://staging.example.com/api",
            "force_update": True,
            "limit": 10,
        }
        dry_run, filter_after_in_days, filter_statuses, prod_env, validator_endpoint, force_update, limit = get_parameters(payload)
        self.assertFalse(dry_run)
        self.assertEqual(filter_after_in_days, 30)
        self.assertEqual(filter_statuses, ["active"])
        self.assertEqual(validator_endpoint, "https://staging.example.com/api")
        self.assertTrue(force_update)
        self.assertEqual(limit, 10)

    def test_string_coercion(self):
        payload = {"dry_run": "false", "force_update": "true", "limit": "5"}
        dry_run, _, _, _, _, force_update, limit = get_parameters(payload)
        self.assertFalse(dry_run)
        self.assertTrue(force_update)
        self.assertEqual(limit, 5)


class TestRebuildMissingValidationReports(unittest.TestCase):
    def _make_session_mock(self, datasets=None):
        """Create a mock DB session returning given datasets from the query."""
        session = MagicMock()
        query_mock = MagicMock()
        query_mock.select_from.return_value = query_mock
        query_mock.join.return_value = query_mock
        query_mock.outerjoin.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.distinct.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = datasets or []
        session.query.return_value = query_mock
        return session

    @patch(f"{_MODULE}._get_validator_version", return_value="7.0.0")
    @patch(f"{_MODULE}._filter_datasets_with_existing_blob", return_value=[])
    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_dry_run_returns_count_without_triggering(
        self, tracker_cls, filter_blob_mock, version_mock
    ):
        session = self._make_session_mock(datasets=[("feed-1", "ds-1"), ("feed-2", "ds-2")])
        filter_blob_mock.return_value = [("feed-1", "ds-1"), ("feed-2", "ds-2")]

        result = rebuild_missing_validation_reports(
            validator_endpoint="https://staging.example.com/api",
            dry_run=True,
            db_session=session,
        )

        self.assertEqual(result["total_candidates"], 2)
        self.assertEqual(result["total_triggered"], 0)
        self.assertIn("dry_run", result["params"])
        self.assertTrue(result["params"]["dry_run"])
        tracker_cls.return_value.start_run.assert_not_called()

    @patch(f"{_MODULE}._get_validator_version", return_value="7.0.0")
    @patch(f"{_MODULE}._filter_datasets_with_existing_blob")
    @patch(f"{_MODULE}.execute_workflows", return_value=["ds-1", "ds-2"])
    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_triggers_workflows_when_not_dry_run(
        self, tracker_cls, exec_mock, filter_blob_mock, version_mock
    ):
        datasets = [("feed-1", "ds-1"), ("feed-2", "ds-2")]
        filter_blob_mock.return_value = datasets
        session = self._make_session_mock(datasets=datasets)

        result = rebuild_missing_validation_reports(
            validator_endpoint="https://staging.example.com/api",
            dry_run=False,
            db_session=session,
        )

        exec_mock.assert_called_once()
        self.assertEqual(result["total_triggered"], 2)
        self.assertFalse(result["params"]["dry_run"])

    @patch(f"{_MODULE}._get_validator_version", return_value="7.0.0")
    @patch(f"{_MODULE}._filter_datasets_with_existing_blob")
    @patch(f"{_MODULE}.execute_workflows", return_value=["ds-1"])
    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_limit_slices_datasets(
        self, tracker_cls, exec_mock, filter_blob_mock, version_mock
    ):
        datasets = [(f"feed-{i}", f"ds-{i}") for i in range(20)]
        filter_blob_mock.return_value = datasets
        session = self._make_session_mock(datasets=datasets)

        result = rebuild_missing_validation_reports(
            validator_endpoint="https://staging.example.com/api",
            dry_run=False,
            limit=5,
            db_session=session,
        )

        _, call_kwargs = exec_mock.call_args
        triggered_datasets = exec_mock.call_args[0][0]
        self.assertEqual(len(triggered_datasets), 5)
        self.assertEqual(result["total_candidates"], 20)
        self.assertEqual(result["total_in_call"], 5)

    @patch(f"{_MODULE}._get_validator_version", return_value="7.0.0")
    @patch(f"{_MODULE}._filter_datasets_with_existing_blob", return_value=[("f", "ds-1")])
    @patch(f"{_MODULE}.execute_workflows", return_value=["ds-1"])
    @patch(f"{_MODULE}.TaskExecutionTracker")
    def test_bypass_db_update_set_for_non_default_endpoint(
        self, tracker_cls, exec_mock, filter_blob_mock, version_mock
    ):
        session = self._make_session_mock(datasets=[("f", "ds-1")])
        rebuild_missing_validation_reports(
            validator_endpoint="https://staging.example.com/api",
            dry_run=False,
            db_session=session,
        )
        _, call_kwargs = exec_mock.call_args
        self.assertTrue(call_kwargs["bypass_db_update"])

    @patch(f"{_MODULE}.rebuild_missing_validation_reports")
    def test_handler_passes_all_params(self, rebuild_mock):
        rebuild_mock.return_value = {"message": "ok"}
        payload = {
            "dry_run": False,
            "filter_after_in_days": 30,
            "validator_endpoint": "https://staging.example.com/api",
            "force_update": True,
            "limit": 10,
        }
        rebuild_missing_validation_reports_handler(payload)
        rebuild_mock.assert_called_once_with(
            validator_endpoint="https://staging.example.com/api",
            dry_run=False,
            filter_after_in_days=30,
            filter_statuses=None,
            prod_env=False,
            force_update=True,
            limit=10,
        )

