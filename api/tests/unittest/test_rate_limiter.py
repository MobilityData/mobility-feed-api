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
import pytest

from shared.common.rate_limiter import (
    RateLimiter,
    get_rate_limiter,
    reset_rate_limiter,
)


class FakeClock:
    """Deterministic clock whose time only advances when ``sleep`` is called."""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def _limiter(rate, capacity=None):
    clock = FakeClock()
    limiter = RateLimiter(rate, capacity=capacity, clock=clock.time, sleep=clock.sleep)
    return limiter, clock


def test_burst_up_to_capacity_does_not_sleep():
    limiter, clock = _limiter(rate=10, capacity=5)
    for _ in range(5):
        waited = limiter.acquire()
        assert waited == 0.0
    assert clock.slept == []


def test_exceeding_capacity_sleeps_deficit_over_rate():
    limiter, clock = _limiter(rate=10, capacity=2)
    assert limiter.acquire() == 0.0
    assert limiter.acquire() == 0.0
    # Bucket empty; next token requires waiting 1 token / 10 per sec = 0.1s.
    waited = limiter.acquire()
    assert waited == pytest.approx(0.1)
    assert clock.slept == [pytest.approx(0.1)]


def test_tokens_refill_over_time():
    limiter, clock = _limiter(rate=10, capacity=1)
    assert limiter.acquire() == 0.0  # empties the bucket
    # Advance 0.5s worth of refill (5 tokens, capped at capacity=1).
    clock.now += 0.5
    waited = limiter.acquire()
    assert waited == 0.0  # refilled, no sleep needed


def test_acquire_multiple_tokens_at_once():
    limiter, clock = _limiter(rate=4, capacity=4)
    # Need 6 tokens but only 4 available -> wait for 2 / 4 = 0.5s.
    waited = limiter.acquire(6)
    assert waited == pytest.approx(0.5)


def test_acquire_zero_is_noop():
    limiter, clock = _limiter(rate=1, capacity=1)
    assert limiter.acquire(0) == 0.0
    assert clock.slept == []


def test_context_manager_acquires_one_token():
    limiter, clock = _limiter(rate=10, capacity=1)
    with limiter:
        pass
    # Bucket now empty; a direct acquire must wait.
    assert limiter.acquire() == pytest.approx(0.1)


def test_invalid_rate_and_capacity_raise():
    with pytest.raises(ValueError):
        RateLimiter(0)
    with pytest.raises(ValueError):
        RateLimiter(-1)
    with pytest.raises(ValueError):
        RateLimiter(10, capacity=0)


def test_registry_returns_same_instance_for_same_name():
    reset_rate_limiter("unit-test-api")
    a = get_rate_limiter("unit-test-api", rate=5)
    b = get_rate_limiter("unit-test-api", rate=999)  # rate ignored after first
    assert a is b
    assert a.rate == 5
    reset_rate_limiter("unit-test-api")


def test_registry_distinct_names_are_independent():
    reset_rate_limiter()
    a = get_rate_limiter("api-a", rate=1)
    b = get_rate_limiter("api-b", rate=2)
    assert a is not b
    assert (a.rate, b.rate) == (1, 2)
    reset_rate_limiter()


def test_reset_rate_limiter_clears_instance():
    a = get_rate_limiter("resettable", rate=1)
    reset_rate_limiter("resettable")
    b = get_rate_limiter("resettable", rate=3)
    assert a is not b
    assert b.rate == 3
    reset_rate_limiter("resettable")
