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

import json
import math
import sys
import unittest
from unittest.mock import MagicMock, patch


class TestCreateWebRevalidationTask(unittest.TestCase):
    def setUp(self):
        # google-cloud-tasks is not installed in the test environment.
        # Provide a MagicMock so `from google.cloud import tasks_v2` succeeds
        # for tests that proceed past the early-return guards.
        self._mock_tasks_v2 = MagicMock()
        self._sys_modules_patcher = patch.dict(sys.modules, {"google.cloud.tasks_v2": self._mock_tasks_v2})
        self._sys_modules_patcher.start()

    def tearDown(self):
        self._sys_modules_patcher.stop()

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
        mock_create_task.side_effect = Exception("409 ALREADY_EXISTS: task already exists")
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


_BATCH_ENV = {
    "PROJECT_ID": "test-project",
    "WEB_REVALIDATION_QUEUE": "web-revalidation-queue",
    "GCP_REGION": "us-central1",
    "ENVIRONMENT": "dev",
    "SERVICE_ACCOUNT_EMAIL": "test@test.iam.gserviceaccount.com",
}


class TestCreateWebRevalidationBatchTasks(unittest.TestCase):
    """The batched enqueue: a list of feeds per task, not a task per feed.

    This is what lets the nightly seal run revalidate every feed it changed. One task per feed
    against a queue that dispatches one per second is what made a catalogue-wide night look
    like it needed a cap, and a cap means leaving pages stale for the website's 14-day expiry.
    """

    def setUp(self):
        # google-cloud-tasks is not installed in the test environment, as above.
        self._mock_tasks_v2 = MagicMock()
        self._sys_modules_patcher = patch.dict(sys.modules, {"google.cloud.tasks_v2": self._mock_tasks_v2})
        self._sys_modules_patcher.start()

    def tearDown(self):
        self._sys_modules_patcher.stop()

    def test_empty_feed_ids(self):
        from shared.common.gcp_utils import create_web_revalidation_batch_tasks

        self.assertEqual(create_web_revalidation_batch_tasks([], dedup_key="k"), 0)

    @patch.dict("os.environ", dict(_BATCH_ENV, WEB_REVALIDATION_QUEUE=""))
    def test_missing_queue_env_var(self):
        from shared.common.gcp_utils import create_web_revalidation_batch_tasks

        self.assertEqual(create_web_revalidation_batch_tasks(["mdb-1"], dedup_key="k"), 0)

    @patch("shared.common.gcp_utils.create_http_task_with_name")
    @patch.dict("os.environ", _BATCH_ENV)
    def test_one_task_carries_many_feeds(self, mock_create_task):
        from shared.common.gcp_utils import create_web_revalidation_batch_tasks

        tasks = create_web_revalidation_batch_tasks(["mdb-1", "mdb-2", "mdb-3"], dedup_key="run-1")

        self.assertEqual(tasks, 1)
        self.assertEqual(mock_create_task.call_count, 1)
        body = mock_create_task.call_args.kwargs["body"]
        for stable_id in (b"mdb-1", b"mdb-2", b"mdb-3"):
            self.assertIn(stable_id, body)

    @patch("shared.common.gcp_utils.create_http_task_with_name")
    @patch.dict("os.environ", _BATCH_ENV)
    def test_chunks_split_at_the_boundary_and_keep_every_feed(self, mock_create_task):
        from shared.common.gcp_utils import create_web_revalidation_batch_tasks

        feeds = [f"mdb-{index}" for index in range(25)]
        tasks = create_web_revalidation_batch_tasks(feeds, dedup_key="run-1", chunk_size=10)

        self.assertEqual(tasks, 3, "10 + 10 + a remainder of 5")
        self.assertEqual(mock_create_task.call_count, 3)

        enqueued = []
        for call in mock_create_task.call_args_list:
            enqueued.extend(json.loads(call.kwargs["body"])["payload"]["feed_stable_ids"])
        self.assertEqual(enqueued, feeds, "every feed exactly once, in order")

    @patch("shared.common.gcp_utils.create_http_task_with_name")
    @patch.dict("os.environ", _BATCH_ENV)
    def test_no_cap_at_any_volume(self, mock_create_task):
        """The regression guard: a whole catalogue goes out, in a sane number of tasks."""
        from shared.common.gcp_utils import WEB_REVALIDATION_CHUNK_SIZE, create_web_revalidation_batch_tasks

        feeds = [f"mdb-{index}" for index in range(2900)]
        tasks = create_web_revalidation_batch_tasks(feeds, dedup_key="run-1")

        enqueued = []
        for call in mock_create_task.call_args_list:
            enqueued.extend(json.loads(call.kwargs["body"])["payload"]["feed_stable_ids"])
        self.assertEqual(len(enqueued), 2900, "every feed, none dropped")
        self.assertEqual(tasks, math.ceil(2900 / WEB_REVALIDATION_CHUNK_SIZE))

    @patch("shared.common.gcp_utils.create_http_task_with_name")
    @patch.dict("os.environ", _BATCH_ENV)
    def test_task_names_key_on_the_dedup_key_and_chunk(self, mock_create_task):
        """A redelivery of the same unit of work produces the same names, so Cloud Tasks
        refuses the duplicates."""
        from shared.common.gcp_utils import create_web_revalidation_batch_tasks

        create_web_revalidation_batch_tasks(
            [f"mdb-{index}" for index in range(3)], dedup_key="seal-run7-batch-0003", chunk_size=1
        )

        names = [call.kwargs["task_name"] for call in mock_create_task.call_args_list]
        self.assertEqual(
            names,
            [
                "revalidate-batch-seal-run7-batch-0003-0000",
                "revalidate-batch-seal-run7-batch-0003-0001",
                "revalidate-batch-seal-run7-batch-0003-0002",
            ],
        )

    @patch("shared.common.gcp_utils.create_http_task_with_name")
    @patch.dict("os.environ", _BATCH_ENV)
    def test_tasks_dispatch_immediately(self, mock_create_task):
        """No bounce window: it exists to collapse repeat calls for one feed, and a run-scoped
        dedup key has nothing to collapse."""
        from shared.common.gcp_utils import create_web_revalidation_batch_tasks

        create_web_revalidation_batch_tasks(["mdb-1"], dedup_key="run-1")

        self.assertIsNone(mock_create_task.call_args.kwargs["task_time"])

    @patch("shared.common.gcp_utils.create_http_task_with_name")
    @patch.dict("os.environ", _BATCH_ENV)
    def test_targets_the_revalidate_feed_task(self, mock_create_task):
        from shared.common.gcp_utils import create_web_revalidation_batch_tasks

        create_web_revalidation_batch_tasks(["mdb-1"], dedup_key="run-1")

        body = json.loads(mock_create_task.call_args.kwargs["body"])
        self.assertEqual(body["task"], "revalidate_feed")
        self.assertEqual(body["payload"], {"feed_stable_ids": ["mdb-1"]})
        self.assertIn("tasks_executor-dev", mock_create_task.call_args.kwargs["url"])

    @patch("shared.common.gcp_utils.create_http_task_with_name")
    @patch.dict("os.environ", _BATCH_ENV)
    def test_an_enqueue_failure_is_logged_not_raised(self, mock_create_task):
        from shared.common.gcp_utils import create_web_revalidation_batch_tasks

        mock_create_task.side_effect = Exception("boom")

        # Should not raise; the seal batch's rows are already committed.
        self.assertEqual(create_web_revalidation_batch_tasks(["mdb-1"], dedup_key="run-1"), 0)


if __name__ == "__main__":
    unittest.main()
