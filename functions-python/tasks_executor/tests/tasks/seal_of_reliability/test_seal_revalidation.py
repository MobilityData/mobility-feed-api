#
#   MobilityData 2026
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
from unittest.mock import patch

from tasks.seal_of_reliability.revalidation import revalidate_changed_feeds

MODULE = "tasks.seal_of_reliability.revalidation.create_web_revalidation_batch_tasks"
KEY = "seal-20260914T040000-batch-0000"


class TestRevalidateChangedFeeds(unittest.TestCase):
    def test_enqueues_every_changed_feed(self):
        with patch(MODULE, return_value=1) as enqueue:
            result = revalidate_changed_feeds(
                ["mdb-1", "mdb-2", "mdb-3"], dedup_key=KEY
            )

        enqueue.assert_called_once_with(["mdb-1", "mdb-2", "mdb-3"], dedup_key=KEY)
        self.assertEqual(result, {"feeds_revalidated": 3, "revalidation_tasks": 1})

    def test_no_changes_enqueues_nothing(self):
        with patch(MODULE) as enqueue:
            result = revalidate_changed_feeds([], dedup_key=KEY)

        enqueue.assert_not_called()
        self.assertEqual(result, {"feeds_revalidated": 0, "revalidation_tasks": 0})

    def test_the_dedup_key_is_passed_through(self):
        """It is what makes a Cloud Tasks redelivery of a seal batch enqueue nothing new."""
        with patch(MODULE, return_value=1) as enqueue:
            revalidate_changed_feeds(["mdb-1"], dedup_key="seal-run-7-batch-0003")

        self.assertEqual(enqueue.call_args.kwargs["dedup_key"], "seal-run-7-batch-0003")

    def test_an_exception_from_the_enqueue_helper_propagates_to_its_caller(self):
        # The helper itself swallows its errors; this asserts the module adds no second
        # try/except, so the one in the worker stays the single place that decides a failed
        # cache bust must not fail the batch.
        with patch(MODULE, side_effect=RuntimeError("cloud tasks down")):
            with self.assertRaises(RuntimeError):
                revalidate_changed_feeds(["mdb-1"], dedup_key=KEY)


if __name__ == "__main__":
    unittest.main()
