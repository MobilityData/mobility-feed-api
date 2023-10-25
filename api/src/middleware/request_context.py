from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.datastructures import Headers
from utils.logger import Logger

REQUEST_CTX_KEY = "request_context_key"
_request_context: ContextVar[dict] = ContextVar(REQUEST_CTX_KEY, default=None)


def get_request_context():
    return _request_context.get()


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = Logger(RequestContextMiddleware.__module__).get_logger()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = Headers(scope=scope)
            context = dict(headers=headers.items())
            _request_context.set(context)
            self.logger.info(f"Set request context {context})")
        await self.app(scope, receive, send)
