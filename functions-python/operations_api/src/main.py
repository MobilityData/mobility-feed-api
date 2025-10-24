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

from flask import Request, Response
from fastapi import FastAPI
from feeds_gen.apis.operations_api import router as FeedsApiRouter
import functions_framework
import asyncio

from middleware.request_context_middleware import RequestContextMiddleware
from shared.helpers.logger import init_logger

init_logger()

app = FastAPI(
    title="Mobility Database Catalog Operations",
    description="API for the Mobility Database Catalog Operations.",
    version="1.0.0",
)

# Add here middlewares that should be applied to all routes.
app.add_middleware(RequestContextMiddleware)
app.include_router(FeedsApiRouter)


def build_scope_from_wsgi(request: Request) -> dict:
    """
    Build the ASGI scope dynamically from a Flask (WSGI) request.
    """
    environ = request.environ

    connection_type = "http"
    if environ.get("HTTP_UPGRADE", "").lower() == "websocket":
        connection_type = "websocket"

    client = (environ.get("REMOTE_ADDR", ""), int(environ.get("REMOTE_PORT", 0)))
    server = (environ.get("SERVER_NAME", ""), int(environ.get("SERVER_PORT", 0)))

    headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in request.headers.items()
    ]

    return {
        "type": connection_type,
        "http_version": environ.get("SERVER_PROTOCOL", "HTTP/1.1").split("/")[1],
        "method": request.method,
        "headers": headers,
        "path": environ.get("PATH_INFO", "/"),
        "raw_path": environ.get("RAW_URI", "").encode("latin-1"),
        "query_string": environ.get("QUERY_STRING", "").encode("latin-1"),
        "server": server,
        "client": client,
        "scheme": environ.get("wsgi.url_scheme", "http"),
    }


@functions_framework.http
def main(request: Request):
    """
    Entry point for Google Cloud Function.
    """
    scope = build_scope_from_wsgi(request)

    async def receive():
        body = request.get_data()
        return {"type": "http.request", "body": body, "more_body": False}

    send_response = {}

    async def send(message):
        if message["type"] == "http.response.start":
            send_response["status"] = message["status"]
            send_response["headers"] = {
                key.decode("latin-1"): value.decode("latin-1")
                for key, value in message["headers"]
            }
        elif message["type"] == "http.response.body":
            send_response["body"] = message.get("body", b"")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(app(scope, receive, send))

        return Response(
            response=send_response.get("body", b""),
            status=send_response.get("status", 200),
            headers=send_response.get("headers", {}),
        )
    except Exception as e:
        return Response(
            response=str(e),
            status=500,
        )
