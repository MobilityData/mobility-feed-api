#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
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


class TestCreateWebRevalidationTask(unittest.TestCase):
    def test_empty_feed_ids(self):
        """Should return early without creating any tasks."""
        from shared.common.gcp_utils import create_web_revalidation_task

        # Should not raise
        create_web_revalidation_task([])

    @patch.dict(
        "os.environ",
        {
            "PROJECT_ID": "test-project",
            "WEB_REVALIDATION_QUEUE": "",
            "GCP_REGION": "us-central1",
            "ENVIRONMENT": "dev",
        },
    )
    def test_missing_queue_env_var(self):
        """Should log a warning and return without creating tasks."""
        from shared.common.gcp_utils import create_web_revalidation_task

        # Should not raise
        create_web_revalidation_task(["mdb-123"])

    @patch("shared.common.gcp_utils.create_http_task_with_name")
    @patch.dict(
        "os.environ",
        {
            "PROJECT_ID": "test-project",
            "WEB_REVALIDATION_QUEUE": "web-revalidation-queue",
            "GCP_REGION": "us-central1",
            "ENVIRONMENT": "dev",
            "SERVICE_ACCOUNT_EMAIL": "test@test.iam.gserviceaccount.com",
        },
    )
    def test_creates_tasks_for_each_feed(self, mock_create_task):
        """Should create one Cloud Task per feed stable ID."""
        from shared.common.gcp_utils import create_web_revalidation_task

        create_web_revalidation_task(["mdb-100", "mdb-200"])

        self.assertEqual(mock_create_task.call_count, 2)

        # Verify the task bodies contain the correct feed IDs
        first_call_body = mock_create_task.call_args_list[0]
        second_call_body = mock_create_task.call_args_list[1]

        self.assertIn(b"mdb-100", first_call_body.kwargs.get("body", b""))
        self.assertIn(b"mdb-200", second_call_body.kwargs.get("body", b""))

    @patch("shared.common.gcp_utils.create_http_task_with_name")
    @patch.dict(
        "os.environ",
        {
            "PROJECT_ID": "test-project",
            "WEB_REVALIDATION_QUEUE": "web-revalidation-queue",
            "GCP_REGION": "us-central1",
            "ENVIRONMENT": "dev",
            "SERVICE_ACCOUNT_EMAIL": "test@test.iam.gserviceaccount.com",
        },
    )
    def test_dedup_task_name_contains_feed_id(self, mock_create_task):
        """Task name should include the feed stable ID for deduplication."""
        from shared.common.gcp_utils import create_web_revalidation_task

        create_web_revalidation_task(["mdb-42"])

        self.assertEqual(mock_create_task.call_count, 1)
        task_name = mock_create_task.call_args.kwargs.get("task_name", "")
        self.assertTrue(task_name.startswith("revalidate-mdb-42-"))

    @patch("shared.common.gcp_utils.create_http_task_with_name")
    @patch.dict(
        "os.environ",
        {
            "PROJECT_ID": "test-project",
            "WEB_REVALIDATION_QUEUE": "web-revalidation-queue",
            "GCP_REGION": "us-central1",
            "ENVIRONMENT": "dev",
            "SERVICE_ACCOUNT_EMAIL": "test@test.iam.gserviceaccount.com",
        },
    )
    def test_already_exists_is_handled_gracefully(self, mock_create_task):
        """ALREADY_EXISTS errors should be caught and logged, not raised."""
        mock_create_task.side_effect = Exception(
            "409 ALREADY_EXISTS: task already exists"
        )
        from shared.common.gcp_utils import create_web_revalidation_task

        # Should not raise
        create_web_revalidation_task(["mdb-123"])

    @patch("shared.common.gcp_utils.create_http_task_with_name")
    @patch.dict(
        "os.environ",
        {
            "PROJECT_ID": "test-project",
            "WEB_REVALIDATION_QUEUE": "web-revalidation-queue",
            "GCP_REGION": "us-central1",
            "ENVIRONMENT": "dev",
            "SERVICE_ACCOUNT_EMAIL": "test@test.iam.gserviceaccount.com",
        },
    )
    def test_targets_tasks_executor_url(self, mock_create_task):
        """Tasks should target the tasks_executor Cloud Function URL."""
        from shared.common.gcp_utils import create_web_revalidation_task

        create_web_revalidation_task(["mdb-1"])

        url = mock_create_task.call_args.kwargs.get("url", "")
        self.assertIn("tasks_executor-dev", url)
        self.assertIn("us-central1", url)


if __name__ == "__main__":
    unittest.main()
