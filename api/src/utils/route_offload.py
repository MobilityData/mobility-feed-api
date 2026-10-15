#
#   MobilityData 2024
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
"""Utilities to keep blocking endpoints off the event loop.

The code generated for the user service declares every route as ``async def`` but
the route bodies are fully synchronous: they simply call into a synchronous impl
that performs blocking I/O (database access and Brevo HTTP calls). FastAPI runs
``async def`` path operations directly on the event loop, so a single slow Brevo
call freezes the entire API for every concurrent request.

``offload_blocking_routes`` rewrites those coroutine endpoints into plain
synchronous functions. FastAPI then dispatches them through the anyio threadpool
(see ``fastapi.routing.run_endpoint_function``), so blocking work no longer stalls
the event loop and other requests stay responsive.
"""

import asyncio
import functools

from fastapi import APIRouter
from fastapi.routing import APIRoute


def _to_sync_endpoint(coroutine_endpoint):
    """Wrap a coroutine endpoint whose body is synchronous into a plain function.

    The generated user-service endpoints contain no ``await`` expressions, so the
    underlying coroutine completes on the first step. Driving it once and reading
    the ``StopIteration`` value yields the same result while letting FastAPI run
    the wrapper in a threadpool instead of on the event loop.
    """

    @functools.wraps(coroutine_endpoint)
    def sync_endpoint(*args, **kwargs):
        coro = coroutine_endpoint(*args, **kwargs)
        try:
            coro.send(None)
        except StopIteration as stop:
            return stop.value
        else:
            coro.close()
            raise RuntimeError(
                f"Endpoint {coroutine_endpoint.__qualname__} awaited; it cannot be "
                "offloaded to a threadpool. Remove it from offload_blocking_routes."
            )

    return sync_endpoint


def offload_blocking_routes(router: APIRouter) -> APIRouter:
    """Convert every coroutine route in ``router`` to run in the threadpool.

    Must be called before ``app.include_router(router)`` so FastAPI builds the
    route handlers from the synchronous endpoints.
    """
    for route in router.routes:
        if isinstance(route, APIRoute) and asyncio.iscoroutinefunction(route.endpoint):
            route.endpoint = _to_sync_endpoint(route.endpoint)
    return router
