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
from unittest.mock import patch

from shared.common.rate_limiter import reset_rate_limiter
from shared.notifications.brevo_notification_sender import (
    DEFAULT_BREVO_MAX_RPS,
    get_brevo_rate_limiter,
)


def _fresh():
    reset_rate_limiter("brevo")


def test_default_rps_when_env_unset():
    _fresh()
    with patch.dict("os.environ", {}, clear=False):
        import os

        os.environ.pop("BREVO_MAX_RPS", None)
        limiter = get_brevo_rate_limiter()
        assert limiter.rate == DEFAULT_BREVO_MAX_RPS
    _fresh()


def test_env_override_sets_rate():
    _fresh()
    with patch.dict("os.environ", {"BREVO_MAX_RPS": "250"}):
        limiter = get_brevo_rate_limiter()
        assert limiter.rate == 250.0
    _fresh()


def test_invalid_env_falls_back_to_default():
    _fresh()
    with patch.dict("os.environ", {"BREVO_MAX_RPS": "not-a-number"}):
        limiter = get_brevo_rate_limiter()
        assert limiter.rate == DEFAULT_BREVO_MAX_RPS
    _fresh()


def test_non_positive_env_falls_back_to_default():
    _fresh()
    with patch.dict("os.environ", {"BREVO_MAX_RPS": "0"}):
        limiter = get_brevo_rate_limiter()
        assert limiter.rate == DEFAULT_BREVO_MAX_RPS
    _fresh()


def test_singleton_shared_across_calls():
    _fresh()
    with patch.dict("os.environ", {"BREVO_MAX_RPS": "500"}):
        first = get_brevo_rate_limiter()
        second = get_brevo_rate_limiter()
        assert first is second
    _fresh()
