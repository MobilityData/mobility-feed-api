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
import time
import unittest
from unittest.mock import MagicMock, patch

from runtime_metrics import MemorySampler, _max_rss_bytes, track_metrics


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


class TestMemorySampler(unittest.TestCase):
    """A number named `peak` has to be one."""

    def test_it_reports_a_peak_rather_than_the_end_state(self):
        sampler = MemorySampler(interval=0.01).start()
        held = [bytearray(16 * 1024 * 1024) for _ in range(8)]
        time.sleep(0.1)
        at_peak = sampler.peak_vms_bytes
        del held
        time.sleep(0.05)
        metrics = sampler.stop()

        self.assertGreaterEqual(metrics["peak_vms_bytes"], at_peak)
        self.assertGreater(metrics["peak_rss_bytes"], 0)

    def test_a_span_shorter_than_the_interval_still_reports(self):
        """The first reading is taken on start, not on the first tick."""
        metrics = MemorySampler(interval=60).start().stop()

        self.assertGreater(metrics["peak_vms_bytes"], 0)

    def test_an_unreadable_process_is_not_fatal(self):
        with patch(
            "runtime_metrics.psutil.Process", side_effect=RuntimeError("no /proc")
        ):
            metrics = MemorySampler(interval=0.01).start().stop()

        self.assertIsNone(metrics["peak_vms_bytes"])
        self.assertIsNone(metrics["peak_rss_bytes"])

    def test_the_thread_does_not_outlive_the_span(self):
        sampler = MemorySampler(interval=0.01).start()
        thread = sampler._thread
        sampler.stop()

        self.assertTrue(thread.daemon)
        self.assertFalse(thread.is_alive())

    def test_it_works_as_a_context_manager(self):
        with MemorySampler(interval=0.01) as sampler:
            pass

        self.assertGreater(sampler.metrics()["peak_vms_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
