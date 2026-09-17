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
"""Publishing how far a build has got, without writing to the database per event.

The viewer polls roughly twice a second, and a multi-gigabyte feed emits an event per
zip member - thousands of them. Forwarding each one would mean thousands of
transactions competing with ordinary API traffic to serve a reading nobody can see
change that fast.

So the writes are throttled to what a reader can actually perceive, with one exception
that matters: a phase change is always written immediately. Phases are what the viewer
turns into words ("Unzipping", "Converting"), and dropping one because it landed inside
a quiet window would leave the interface describing the wrong step.

Each write also renews the build's claim on the dataset, so a long conversion keeps its
lock by reporting progress rather than by a separate keepalive.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

# Phases, matching what the viewer already knows how to word. `upload` is publishing to
# the bucket; there is no phase for the local write, which happens under `convert`.
PHASE_START = "start"
PHASE_DOWNLOAD = "download"
PHASE_EXTRACT = "extract"
PHASE_CONVERT = "convert"
PHASE_UPLOAD = "upload"
PHASE_SUMMARISE = "summarise"
PHASE_DONE = "done"

DEFAULT_MIN_INTERVAL_S = 1.0


class ThrottledProgress:
    """Collects progress events and publishes the ones worth publishing.

    `publish` is handed the full state each time rather than a delta, so a reader that
    missed writes is never behind - it simply sees fewer intermediate readings.
    """

    def __init__(
        self,
        publish: Callable[[dict[str, Any]], None],
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        clock: Callable[[], float] = time.monotonic,
        logger: Optional[logging.Logger] = None,
    ):
        self._publish = publish
        self._min_interval_s = min_interval_s
        self._clock = clock
        self._logger = logger or logging.getLogger(__name__)
        self._last_phase: Optional[str] = None
        self._last_write_at: Optional[float] = None
        self.last_state: Optional[dict[str, Any]] = None

    def __call__(
        self, phase: str, done: int = 0, total: int = 0, detail: str = ""
    ) -> None:
        """A `ProgressFn`, so it can be passed straight to the converter."""
        state = {
            "phase": phase,
            "done": int(done),
            "total": int(total),
            "detail": detail,
        }
        self.last_state = state

        now = self._clock()
        phase_changed = phase != self._last_phase
        due = (
            self._last_write_at is None
            or (now - self._last_write_at) >= self._min_interval_s
        )
        if not (phase_changed or due):
            return

        self._last_phase = phase
        self._last_write_at = now
        self._write(state)

    def flush(self, **overrides: Any) -> None:
        """Publish the current reading regardless of the interval.

        For the end of a phase whose final count would otherwise be dropped, and for
        the terminal states, where the last thing written is what a reader is left
        looking at.
        """
        state = {
            **(
                self.last_state
                or {"phase": PHASE_START, "done": 0, "total": 0, "detail": ""}
            ),
            **overrides,
        }
        self.last_state = state
        self._last_phase = state.get("phase")
        self._last_write_at = self._clock()
        self._write(state)

    def _write(self, state: dict[str, Any]) -> None:
        try:
            self._publish(state)
        except Exception as error:
            # Progress is a courtesy; a build must not fail because a reading could not
            # be recorded. The claim is renewed by these same writes, so a sustained
            # outage costs the lease - which is the correct outcome, since a worker
            # that cannot reach the database cannot report failure either.
            self._logger.warning("Could not publish progress %s: %s", state, error)
