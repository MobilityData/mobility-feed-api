from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.datastructures import Headers
from utils.logger import Logger

REQUEST_CTX_KEY = "request_context_key"
_request_context: ContextVar[dict] = ContextVar(REQUEST_CTX_KEY, default=None)


class RequestContext:
    def __init__(self, headers: dict) -> None:
        self.client_host = None
        self.iap_jwt_assertion = None
        self.client_user_agent = None
        self.user_id = None
        self.user_email = None
        self._headers = headers
        self._extract_from_headers(headers)

    def _extract_from_headers(self, headers: dict) -> None:
        self.user_id = headers.get("x-goog-authenticated-user-id")
        self.user_email = headers.get("x-goog-authenticated-user-email")
        self.client_host = headers.get("host")
        self.client_user_agent = headers.get("user-agent")
        self.iap_jwt_assertion = headers.get("x-goog-iap-jwt-assertion")

    def __repr__(self) -> str:
        # Omitting sensitive data like email and jwt assertion
        safe_properties = dict(
            user_id=self.user_id, client_user_agent=self.client_user_agent, client_host=self.client_host
        )
        return f"request-context={safe_properties})"


def get_request_context():
    return _request_context.get()


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = Logger(RequestContextMiddleware.__module__).get_logger()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            request_context = RequestContext(Headers(scope=scope))
            _request_context.set(request_context)
            self.logger.info(f"{request_context})")
        await self.app(scope, receive, send)
