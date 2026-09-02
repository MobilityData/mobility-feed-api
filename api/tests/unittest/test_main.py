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
"""Route-presence regression test.

Forgetting to `app.include_router(...)` a newly generated router 404s every route in it even
though its impl and its tests are green — nothing else catches that. This asserts the routes this
app is supposed to expose are actually registered.
"""

from main import app


def _registered_paths() -> set[str]:
    return {route.path for route in app.routes}


def test_early_access_routes_registered():
    paths = _registered_paths()
    assert "/v1/user/early-access" in paths
