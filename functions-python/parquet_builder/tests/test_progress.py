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
"""What the throttle must and must not drop."""

import unittest

from progress import PHASE_CONVERT, PHASE_DOWNLOAD, PHASE_EXTRACT, ThrottledProgress


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def _recorder():
    written = []
    return written, written.append


class TestThrottledProgress(unittest.TestCase):
    def test_writes_the_first_reading(self):
        written, publish = _recorder()
        progress = ThrottledProgress(publish, clock=FakeClock())

        progress(PHASE_EXTRACT, 1, 10, "stops.txt")

        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["phase"], PHASE_EXTRACT)

    def test_coalesces_events_inside_one_phase(self):
        written, publish = _recorder()
        clock = FakeClock()
        progress = ThrottledProgress(publish, min_interval_s=1.0, clock=clock)

        # A large feed emits thousands of these; the reader polls twice a second.
        for i in range(1, 501):
            progress(PHASE_EXTRACT, i, 500, f"file{i}.txt")

        self.assertEqual(
            len(written), 1, "500 events inside one second must be one write"
        )

    def test_writes_again_once_the_interval_passes(self):
        written, publish = _recorder()
        clock = FakeClock()
        progress = ThrottledProgress(publish, min_interval_s=1.0, clock=clock)

        progress(PHASE_EXTRACT, 1, 10, "a.txt")
        clock.advance(1.5)
        progress(PHASE_EXTRACT, 2, 10, "b.txt")

        self.assertEqual([w["detail"] for w in written], ["a.txt", "b.txt"])

    def test_never_drops_a_phase_change(self):
        """The rule that matters: phases are what the viewer turns into words."""
        written, publish = _recorder()
        clock = FakeClock()
        progress = ThrottledProgress(publish, min_interval_s=1000.0, clock=clock)

        progress(PHASE_DOWNLOAD, 0, 0, "feed.zip")
        progress(PHASE_EXTRACT, 1, 10, "stops.txt")
        progress(PHASE_CONVERT, 1, 5, "stops")

        self.assertEqual(
            [w["phase"] for w in written],
            [PHASE_DOWNLOAD, PHASE_EXTRACT, PHASE_CONVERT],
            "a phase change must be written even deep inside a quiet window",
        )

    def test_flush_writes_regardless_of_the_interval(self):
        written, publish = _recorder()
        clock = FakeClock()
        progress = ThrottledProgress(publish, min_interval_s=1000.0, clock=clock)

        progress(PHASE_CONVERT, 1, 32, "agency")
        progress(PHASE_CONVERT, 32, 32, "trips")  # throttled away
        progress.flush()

        self.assertEqual(len(written), 2)
        self.assertEqual(written[-1]["done"], 32, "the final count must survive")

    def test_flush_overrides_are_applied(self):
        written, publish = _recorder()
        progress = ThrottledProgress(publish, clock=FakeClock())

        progress.flush(phase=PHASE_DOWNLOAD, done=10, total=100, detail="feed.zip")

        self.assertEqual(
            written[-1],
            {"phase": PHASE_DOWNLOAD, "done": 10, "total": 100, "detail": "feed.zip"},
        )

    def test_a_failing_publish_does_not_break_the_build(self):
        """Progress is a courtesy. Losing a reading must not lose the conversion."""

        def explode(_state):
            raise RuntimeError("database went away")

        progress = ThrottledProgress(explode, clock=FakeClock())
        progress(PHASE_CONVERT, 1, 5, "stops")  # must not raise

    def test_ints_are_coerced(self):
        written, publish = _recorder()
        progress = ThrottledProgress(publish, clock=FakeClock())

        progress(PHASE_DOWNLOAD, 1.0, 2.0, "feed.zip")

        self.assertIsInstance(written[0]["done"], int)
        self.assertIsInstance(written[0]["total"], int)


if __name__ == "__main__":
    unittest.main()
