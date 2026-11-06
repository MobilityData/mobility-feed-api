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
"""Route ordering of the generated routers.

Starlette matches routes in the order they were added, and a path parameter matches any segment: a fixed path added
after a parameterized path with the same prefix is never reached. The generated routers declare their operations in
operationId order, so `/v1/locations/{location_id}` (getLocation) comes before `/v1/locations/lookup`
(getLocationByPath), and a request to the lookup endpoint would fail the integer validation of `location_id`.
"""

from fastapi import APIRouter
from fastapi.routing import APIRoute


def fixed_paths_first(router: APIRouter) -> APIRouter:
    """Move the routes without path parameters before the routes with path parameters, keeping their relative order.

    The router is changed in place and returned, to be passed to `include_router`.
    """
    router.routes.sort(key=lambda route: isinstance(route, APIRoute) and bool(route.param_convertors))
    return router
