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
from typing import Final

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from garage.impl.error_handling import feature_not_enabled, missing_or_invalid_token
from shared.common.feature_flags import feature_flag_enabled
from shared.database.users_database import with_users_db_session
from shared.middleware.request_context import RequestContext, _request_context

# Feature flag (feature_flag.id, users DB) that grants a user access to their datasets in the Garage.
# Internal only: the API never names it to clients.
USER_DATASETS_FEATURE_FLAG_ID: Final[str] = "userDatasets"


@with_users_db_session
def garage_enabled(user_id: str, db_session=None) -> bool:
    """Whether the user holds the user datasets feature flag."""
    return feature_flag_enabled(db_session, user_id, USER_DATASETS_FEATURE_FLAG_ID)


class GarageAccessMiddleware:
    """
    Sets the request context from the MDB token, the same way the Feeds API does, and lets a request
    through only when it comes from a user holding the user datasets feature flag.
    Every Garage endpoint needs both, so the check lives here rather than in each endpoint.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_context = RequestContext(scope=scope)
        _request_context.set(request_context.__dict__)

        if not request_context.user_id:
            response = JSONResponse(
                status_code=401, content={"details": missing_or_invalid_token}
            )
        elif not garage_enabled(request_context.user_id):
            response = JSONResponse(
                status_code=403, content={"details": feature_not_enabled}
            )
        else:
            await self.app(scope, receive, send)
            return
        await response(scope, receive, send)
