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
"""Generic, reusable client-side rate limiting.

Provides a thread-safe token-bucket :class:`RateLimiter` and a small named
registry (:func:`get_rate_limiter`) so any outbound API caller can share a
single process-wide bucket keyed by a logical name (e.g. ``"brevo"``,
``"tdg"``). The algorithm is API-agnostic; callers only choose a name and rate.

.. note::
    Scope is **per process**. Each Cloud Function instance / worker process keeps
    its own bucket, so the effective aggregate rate against an external API is
    ``configured_rate * number_of_concurrent_instances``. Size per-process rates
    accordingly (or run a single-instance/serialized caller) when an external
    provider enforces a hard global limit.

Example::

    limiter = get_rate_limiter("tdg", rate=10)  # 10 requests/second
    limiter.acquire()                            # blocks if necessary
    response = requests.get(url)
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Dict, Optional


class RateLimiter:
    """Thread-safe token-bucket rate limiter.

    Tokens refill continuously at ``rate`` tokens per second up to ``capacity``
    (the maximum burst). :meth:`acquire` blocks just long enough to keep the
    effective call rate at or below ``rate``.

    ``clock`` and ``sleep`` are injectable so the limiter can be unit-tested
    deterministically without real time passing.
    """

    def __init__(
        self,
        rate: float,
        capacity: Optional[float] = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if rate <= 0:
            raise ValueError("rate must be greater than 0")
        if capacity is not None and capacity <= 0:
            raise ValueError("capacity must be greater than 0")
        self._rate = float(rate)
        self._capacity = float(capacity if capacity is not None else rate)
        self._clock = clock
        self._sleep = sleep
        self._tokens = self._capacity
        self._timestamp = clock()
        self._lock = threading.Lock()

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def capacity(self) -> float:
        return self._capacity

    def _refill(self) -> None:
        now = self._clock()
        elapsed = now - self._timestamp
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._timestamp = now

    def acquire(self, n: float = 1) -> float:
        """Consume ``n`` tokens, blocking until they are available.

        Returns the number of seconds spent waiting (``0`` when tokens were
        immediately available).

        Tokens are *reserved* atomically under the lock (the bucket is allowed
        to go negative), and the wait that corresponds to a reservation is slept
        **outside** the lock. This keeps the shared bucket consistent while still
        allowing concurrent callers to make progress instead of being serialized
        behind one another's sleep.
        """
        if n <= 0:
            return 0.0
        with self._lock:
            self._refill()
            # Reserve the tokens now; a negative balance represents tokens that
            # future refill will repay, and determines how long this caller waits.
            self._tokens -= n
            waited = 0.0 if self._tokens >= 0 else (-self._tokens) / self._rate
        if waited > 0:
            self._sleep(waited)
        return waited

    def __enter__(self) -> "RateLimiter":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


_registry: Dict[str, RateLimiter] = {}
_registry_lock = threading.Lock()


def get_rate_limiter(
    name: str,
    rate: float,
    capacity: Optional[float] = None,
) -> RateLimiter:
    """Return a process-wide :class:`RateLimiter` shared under ``name``.

    The first caller for a given ``name`` configures the limiter; subsequent
    calls return the same instance and ignore their ``rate``/``capacity``
    arguments. Use :func:`reset_rate_limiter` in tests to reconfigure.
    """
    limiter = _registry.get(name)
    if limiter is None:
        with _registry_lock:
            limiter = _registry.get(name)
            if limiter is None:
                limiter = RateLimiter(rate, capacity=capacity)
                _registry[name] = limiter
    return limiter


def reset_rate_limiter(name: Optional[str] = None) -> None:
    """Drop the cached limiter for ``name`` (or all when ``name`` is None)."""
    with _registry_lock:
        if name is None:
            _registry.clear()
        else:
            _registry.pop(name, None)
