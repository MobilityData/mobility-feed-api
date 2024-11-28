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

import logging
from starlette.types import ASGIApp, Receive, Scope, Send

from operations_api.src.middleware.request_context_oauth2 import (
    RequestContext,
    _request_context,
)

# from operations_api.src.middleware.request_context_middleware import RequestContextMiddleware


class RequestContextMiddleware:
    """
    Middleware to set the request context and authorize requests.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.logger = logging.getLogger()
        self.app = app

    @staticmethod
    def extract_response_info(headers):
        """
        Extracts the content type and content length from the response headers.
        """
        content_type = None
        content_length = None
        for key, value in headers:
            if key == b"content-length":
                content_length = int(value)
            elif key == b"content-type":
                content_type = value
        return content_type, content_length

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Middleware to set the request context and authorize requests.
        """
        if scope["type"] == "http":
            request_context = RequestContext(scope=scope)
            _request_context.set(request_context.__dict__)

            async def http_send(message):
                await send(message)

            await self.app(scope, receive, http_send)
        else:
            await self.app(scope, receive, send)
