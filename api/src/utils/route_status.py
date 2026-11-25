"""Make generated routes answer with the success status their spec documents.

The FastAPI generator records a route's documented responses but always leaves the route's own
``status_code`` at FastAPI's default of 200, so an operation documented as 201 or 204 answers 200.
"""

from fastapi import APIRouter
from fastapi.routing import APIRoute


def use_documented_success_status(router: APIRouter) -> APIRouter:
    """Set each route's status to its only documented 2xx response, when that is not 200.

    Must be called before ``app.include_router(router)``, which copies each route's
    ``status_code`` into the route it registers.
    """
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        success = [int(code) for code in route.responses if 200 <= int(code) < 300]
        if len(success) == 1 and success[0] != 200:
            route.status_code = success[0]
    return router
