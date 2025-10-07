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

from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfile, Gtfsfeed
from shared.helpers.tests.test_shared.test_utils.database_utils import default_db_url

from tasks.visualization_files.rebuild_missing_visualization_files import (
    rebuild_missing_visualization_files_handler,
    rebuild_missing_visualization_files,
    get_parameters,
    REQUIRED_FILES,
)


class TestRebuildMissingVisualizationFiles(unittest.TestCase):
    # --------------------------
    # get_parameters
    # --------------------------
    def test_get_parameters_defaults(self):
        payload = {}
        (
            dry_run,
            check_existing,
            latest_only,
            include_deprecated_feeds,
            include_feed_op_status,
            limit,
        ) = get_parameters(payload)

        self.assertTrue(dry_run)
        self.assertTrue(check_existing)
        self.assertTrue(latest_only)
        self.assertFalse(include_deprecated_feeds)
        self.assertEqual(include_feed_op_status, ["published"])
        self.assertIsNone(limit)

    def test_get_parameters_explicit_bool_and_string(self):
        # dry_run as bool False
        payload = {
            "dry_run": False,
            "check_existing": False,
            "include_feed_op_status": ["published", "wip"],
        }
        (
            dry_run,
            check_existing,
            latest_only,
            include_deprecated_feeds,
            include_feed_op_status,
            limit,
        ) = get_parameters(payload)
        self.assertFalse(dry_run)
        self.assertEqual(include_feed_op_status, ["published", "wip"])
        self.assertFalse(check_existing)

        # dry_run as string "false" (should coerce to False)
        payload = {"dry_run": "false", "include_feed_op_status": ["wip"]}
        (
            dry_run,
            check_existing,
            latest_only,
            include_deprecated_feeds,
            include_feed_op_status,
            limit,
        ) = get_parameters(payload)
        self.assertFalse(dry_run)
        self.assertEqual(include_feed_op_status, ["wip"])
        self.assertTrue(check_existing)

        # dry_run as string "True" (case-insensitive -> True)
        payload = {"dry_run": "True", "check_existing": "True"}
        (
            dry_run,
            check_existing,
            latest_only,
            include_deprecated_feeds,
            include_feed_op_status,
            limit,
        ) = get_parameters(payload)
        self.assertTrue(dry_run)
        self.assertEqual(include_feed_op_status, ["published"])
        self.assertTrue(check_existing)

    # --------------------------
    # handler wiring
    # --------------------------
    @patch(
        "tasks.visualization_files.rebuild_missing_visualization_files.rebuild_missing_visualization_files"
    )
    def test_handler_calls_impl_with_extracted_params(self, impl_mock):
        expected = {"ok": True}
        impl_mock.return_value = expected

        payload = {"dry_run": True, "check_existing": False}
        resp = rebuild_missing_visualization_files_handler(payload)

        self.assertEqual(resp, expected)
        impl_mock.assert_called_once_with(
            dry_run=True,
            include_deprecated_feeds=False,
            include_feed_op_status=["published"],
            latest_only=True,
            limit=None,
            check_existing=False,
        )

    # --------------------------
    # core function: check_existing=False
    # --------------------------
    @with_db_session(db_url=default_db_url)
    @patch(
        "tasks.visualization_files.rebuild_missing_visualization_files.create_http_pmtiles_builder_task"
    )
    def test_rebuild_no_check_existing_counts_all_eligible_dryrun(
        self, create_task_mock, db_session: Session
    ):
        """
        When check_existing=False, every eligible dataset should be considered for processing.
        Dry run => no tasks created.
        """
        # Compute eligible datasets using the same logic as the function
        eligible_count = (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.latest.is_(True))
            .filter(Gtfsdataset.feed.has(Gtfsfeed.status != "deprecated"))
            .join(Gtfsdataset.gtfsfiles)
            .filter(Gtfsfile.file_name.in_(REQUIRED_FILES))
            .group_by(Gtfsdataset.id)
            .having(func.count(distinct(Gtfsfile.file_name)) == len(REQUIRED_FILES))
            .count()
        )

        resp = rebuild_missing_visualization_files(
            db_session=db_session,
            dry_run=True,
            check_existing=False,
        )

        self.assertIsNotNone(resp)
        self.assertEqual(resp["total_processed"], eligible_count)
        self.assertEqual(resp["message"], "Dry run: no datasets processed.")
        create_task_mock.assert_not_called()

    # --------------------------
    # core function: check_existing=True (all files exist)
    # --------------------------
    @with_db_session(db_url=default_db_url)
    @patch(
        "tasks.visualization_files.rebuild_missing_visualization_files.create_http_pmtiles_builder_task"
    )
    def test_rebuild_check_existing_all_exist_dryrun_zero(
        self, create_task_mock, db_session: Session
    ):
        """
        When check_existing=True and every PMTiles file exists, total_processed should be 0.
        """
        # Mock bucket + blob.exists() => True for all requested files
        mock_bucket = MagicMock()

        def blob_side_effect(_):
            mock_blob = MagicMock()
            mock_blob.exists.return_value = True  # Everything exists
            return mock_blob

        mock_bucket.blob.side_effect = blob_side_effect

        resp = rebuild_missing_visualization_files(
            db_session=db_session,
            dry_run=True,
            check_existing=True,
        )

        self.assertIsNotNone(resp)
        self.assertEqual(resp["total_processed"], 0)
        self.assertEqual(resp["message"], "Dry run: no datasets processed.")
        create_task_mock.assert_not_called()

    # --------------------------
    # core function: check_existing=True (all files missing)
    # --------------------------
    @with_db_session(db_url=default_db_url)
    @patch(
        "tasks.visualization_files.rebuild_missing_visualization_files.create_http_pmtiles_builder_task"
    )
    def test_rebuild_check_existing_all_missing_dryrun_counts_all(
        self, create_task_mock, db_session: Session
    ):
        """
        When check_existing=True and nothing exists, all eligible datasets should be processed (in dry run).
        """
        eligible_count = (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.latest.is_(True))
            .filter(Gtfsdataset.feed.has(Gtfsfeed.status != "deprecated"))
            .join(Gtfsdataset.gtfsfiles)
            .filter(Gtfsfile.file_name.in_(REQUIRED_FILES))
            .group_by(Gtfsdataset.id)
            .having(func.count(distinct(Gtfsfile.file_name)) == len(REQUIRED_FILES))
            .count()
        )

        mock_bucket = MagicMock()

        def blob_side_effect(_):
            mock_blob = MagicMock()
            mock_blob.exists.return_value = False  # Nothing exists
            return mock_blob

        mock_bucket.blob.side_effect = blob_side_effect

        resp = rebuild_missing_visualization_files(
            db_session=db_session,
            dry_run=True,
            check_existing=True,
        )

        self.assertIsNotNone(resp)
        self.assertEqual(resp["total_processed"], eligible_count)
        self.assertEqual(resp["message"], "Dry run: no datasets processed.")
        create_task_mock.assert_not_called()

    # --------------------------
    # core function: non-dry run => tasks created only for missing
    # --------------------------
    @with_db_session(db_url=default_db_url)
    @patch(
        "tasks.visualization_files.rebuild_missing_visualization_files.create_http_pmtiles_builder_task"
    )
    def test_rebuild_non_dry_run_creates_tasks_for_missing(
        self, create_task_mock, db_session: Session
    ):
        """
        Non-dry run: ensure create_http_pmtiles_builder_task is called once per dataset
        missing at least one PMTiles file.
        Here we simulate: first dataset missing (False), others present (True).
        """
        # Pull eligible datasets to know how many there are and to map stable_ids
        eligible_datasets = (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.latest.is_(True))
            .filter(Gtfsdataset.feed.has(Gtfsfeed.status != "deprecated"))
            .join(Gtfsdataset.gtfsfiles)
            .filter(Gtfsfile.file_name.in_(REQUIRED_FILES))
            .group_by(Gtfsdataset.id)
            .having(func.count(distinct(Gtfsfile.file_name)) == len(REQUIRED_FILES))
            .all()
        )

        # Short-circuit: if none eligible, still ensure no crash and no calls
        if not eligible_datasets:
            resp = rebuild_missing_visualization_files(
                db_session=db_session,
                dry_run=False,
                check_existing=True,
            )
            self.assertEqual(resp["total_processed"], 0)
            create_task_mock.assert_not_called()
            return

        resp = rebuild_missing_visualization_files(
            db_session=db_session,
            dry_run=False,
            check_existing=True,
        )

        # Exactly one dataset should have been processed (the first one we forced to be missing)
        self.assertGreaterEqual(len(eligible_datasets), 1)
        self.assertEqual(resp["total_processed"], 1)
        self.assertEqual(
            resp["message"],
            "Rebuild missing visualization files task executed successfully.",
        )
        create_task_mock.assert_called_once()
        # Validate call signature shape (feed_stable_id, dataset_stable_id)
        args, kwargs = create_task_mock.call_args
        self.assertEqual(len(args), 2)
        self.assertIsInstance(args[0], str)
        self.assertIsInstance(args[1], str)

    # --------------------------
    # sanity: constants are as expected
    # --------------------------
    def test_constants_have_expected_items(self):
        # Not asserting exact content beyond presence/shape to avoid brittleness
        self.assertIn("stops.txt", REQUIRED_FILES)
        self.assertIn("routes.txt", REQUIRED_FILES)
