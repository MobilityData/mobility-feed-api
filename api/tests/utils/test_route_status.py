from fastapi import APIRouter

from utils.route_status import use_documented_success_status


def _router():
    router = APIRouter()

    @router.post("/created", responses={201: {"description": "Created"}, 422: {"description": "Invalid"}})
    def created():
        return {}

    @router.delete("/deleted", responses={204: {"description": "Deleted"}, 404: {"description": "Missing"}})
    def deleted():
        return None

    @router.get("/ok", responses={200: {"description": "OK"}})
    def ok():
        return {}

    @router.get("/ambiguous", responses={201: {"description": "A"}, 202: {"description": "B"}})
    def ambiguous():
        return {}

    return router


def test_sets_the_only_documented_success_status():
    router = use_documented_success_status(_router())
    status_by_path = {route.path: route.status_code for route in router.routes}
    assert status_by_path["/created"] == 201
    assert status_by_path["/deleted"] == 204
    assert status_by_path["/ok"] is None
    assert status_by_path["/ambiguous"] is None
