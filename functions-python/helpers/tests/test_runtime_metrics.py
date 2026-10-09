#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""The metrics line is what container sizing is read off, so it has to carry RSS."""

import logging
import unittest
from unittest.mock import MagicMock, patch

from runtime_metrics import _max_rss_bytes, track_metrics


def _run(metrics=("time", "memory", "cpu"), body=lambda: 42):
    logger = MagicMock(spec=logging.Logger)

    @track_metrics(metrics=metrics)
    def work(logger=None):
        return body()

    result = work(logger=logger)
    message = logger.info.call_args.args[2] if logger.info.called else ""
    return result, message


class TestMemoryReporting(unittest.TestCase):
    def test_rss_is_reported_alongside_tracemalloc(self):
        """tracemalloc cannot see a C extension's heap; RSS is what the container bills."""
        _, message = _run()

        self.assertIn("memory:", message)
        self.assertIn("rss:", message)
        self.assertIn("process peak:", message)
        # Address space, which is what RLIMIT_AS actually caps. Sizing a container from
        # RSS alone under-provisions it.
        self.assertIn("vms:", message)

    def test_the_existing_fields_are_unchanged(self):
        """Log history stays comparable, so nothing is renamed or dropped."""
        _, message = _run()

        self.assertIn("time:", message)
        self.assertIn("peak:", message)
        self.assertIn("cpu:", message)

    def test_no_memory_metric_means_no_rss(self):
        _, message = _run(metrics=("time",))

        self.assertNotIn("rss:", message)

    def test_an_unreadable_rss_does_not_break_the_line(self):
        """Metrics are a courtesy; they must not fail the function they measure."""
        with patch("runtime_metrics.psutil.Process") as process_cls:
            process = process_cls.return_value
            process.memory_info.side_effect = RuntimeError("no /proc")
            process.cpu_percent.return_value = 0.0

            result, message = _run()

        self.assertEqual(result, 42)
        self.assertIn("memory:", message)
        self.assertNotIn("rss:", message)

    def test_metrics_survive_an_exception_in_the_wrapped_function(self):
        def boom():
            raise ValueError("nope")

        with self.assertRaises(ValueError):
            _run(body=boom)


class TestMaxRss(unittest.TestCase):
    def test_it_returns_a_plausible_byte_count(self):
        """Linux reports ru_maxrss in KiB and macOS in bytes; both must come back as bytes."""
        peak = _max_rss_bytes()

        self.assertGreater(peak, 1024 * 1024, "under 1 MB means the unit is wrong")
        self.assertLess(peak, 100 * 1024**3)


if __name__ == "__main__":
    unittest.main()
