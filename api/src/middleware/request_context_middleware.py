import logging
import time
from starlette.types import ASGIApp, Receive, Scope, Send

from middleware.request_context import RequestContext, _request_context
from utils.logger import HttpRequest, API_ACCESS_LOG


class RequestContextMiddleware:
    """
    Middleware to set the request context and log the API access logs.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.logger = logging.getLogger(API_ACCESS_LOG)
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

    @staticmethod
    def create_http_request(
        scope: Scope, request_context: RequestContext, status_code: int, content_length: int, latency: float
    ) -> HttpRequest:
        """
        Create an HttpRequest object for logging.
        """
        request_method = scope["method"]
        request_path = scope["path"]
        protocol = scope["scheme"].upper() + "/" + str(scope["http_version"])
        return HttpRequest(
            requestMethod=request_method,
            requestUrl=f"{request_context.protocol}://{request_context.host}{request_path}",
            remoteIp=request_context.client_host,
            protocol=protocol,
            status=status_code,
            responseSize=content_length,
            userAgent=request_context.client_user_agent,
            serverIp=request_context.server_ip,
            latency=latency,
        )

    def log_api_access(
        self, scope: Scope, request_context: RequestContext, status_code: int, content_length: int, start_time: float
    ):
        """
        Log the API access logs.
        """
        latency = time.time() - start_time
        request = self.create_http_request(scope, request_context, status_code, content_length, latency)
        self.logger.info(
            "API Access Log",
            extra={
                "context": {
                    "http_request": request,
                }
            },
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Middleware to set the request context and log the API access logs.
        """
        if scope["type"] == "http":
            start_time = time.time()
            request_context = RequestContext(scope=scope)
            _request_context.set(request_context.__dict__)

            async def http_send(message):
                if message["type"] == "http.response.start":
                    content_type, content_length = self.extract_response_info(message["headers"])
                    status_code = message["status"]
                    self.log_api_access(scope, request_context, status_code, content_length, start_time)
                await send(message)

            await self.app(scope, receive, http_send)
        else:
            await self.app(scope, receive, send)
