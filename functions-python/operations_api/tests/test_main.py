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
"""Route-presence regression test: a missing `app.include_router(...)` 404s every route in it
while its impl and tests stay green."""

from main import app


def _registered_paths() -> set[str]:
    return {route.path for route in app.routes}


def test_early_access_routes_registered():
    paths = _registered_paths()
    assert "/v1/operations/early-access-programs" in paths
    assert "/v1/operations/early-access-programs/{id}" in paths
    assert "/v1/operations/early-access-programs/{id}/invited-emails" in paths
    assert "/v1/operations/early-access-programs/{id}/report" in paths
    # Removed, not renamed; a lingering route means a stale generated router.
    assert "/v1/operations/early-access-programs/{id}/feature-flags" not in paths
    assert "/v1/operations/early-access-programs/{id}/enrollments" not in paths
    assert (
        "/v1/operations/early-access-programs/{id}/invited-emails/remove" not in paths
    )


def test_invited_emails_supports_both_add_and_remove():
    """The bulk add and the bulk remove share one path, distinguished by method."""
    methods = {
        method
        for route in app.routes
        if getattr(route, "path", None)
        == "/v1/operations/early-access-programs/{id}/invited-emails"
        for method in route.methods
    }
    assert {"POST", "DELETE"} <= methods
