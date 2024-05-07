from contextvars import ContextVar

import requests
from google.auth import jwt
from requests.exceptions import RequestException
from starlette.datastructures import Headers
from starlette.types import Scope

from utils.config import get_config, PROJECT_ID

REQUEST_CTX_KEY = "request_context_key"
_request_context: ContextVar[dict] = ContextVar(REQUEST_CTX_KEY, default={})


class RequestContext:
    google_public_keys = None

    def __init__(self, scope: Scope) -> None:
        headers = Headers(scope=scope)
        self.headers = headers
        self.scope = scope
        self._extract_from_headers(headers, scope)
        self.resolve_google_public_keys()

    def resolve_google_public_keys(self):
        """
        Returns Google's public keys which can be used to verify the signature of a JWT.
        """
        if self.google_public_keys is None:
            try:
                response = requests.get(
                    "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
                )
                response.raise_for_status()
                self.google_public_keys = response.json()
            except RequestException as e:
                print(f"Error fetching Google's public keys: {e}")

    def decode_jwt(self, token: str):
        """
        :param token: jwt token
        :return:
        """
        try:
            token = token.replace("Bearer ", "")
            self.resolve_google_public_keys()
            if not self.google_public_keys:
                return None
            return jwt.decode(token, self.google_public_keys, audience=get_config(PROJECT_ID))
        except Exception as e:
            print(f"Error decoding JWT: {e}")
            return None

    def _extract_from_headers(self, headers: dict, scope: Scope) -> None:
        self.host = headers.get("host")
        self.protocol = headers.get("x-forwarded-proto") if headers.get("x-forwarded-proto") else scope.get("scheme")
        self.client_host = headers.get("x-forwarded-for")
        self.server_ip = scope.get("server")[0] if scope.get("server") and len(scope.get("server")) > 0 else None
        if not self.client_host:
            self.client_host = scope.get("client")[0] if scope.get("client") and len(scope.get("client")) > 0 else None
        else:
            # X-Forwarded-For: client, proxy1, proxy2
            forwarded_ips = self.client_host.split(",")
            self.client_host = forwarded_ips[0] if len(forwarded_ips) > 0 else self.client_host
            # merge all forwarded ips but the first one
            self.server_ip = ",".join(forwarded_ips[1:]) if len(forwarded_ips) > 1 else self.server_ip
        self.client_user_agent = headers.get("user-agent")
        self.iap_jwt_assertion = headers.get("x-goog-iap-jwt-assertion")
        self.trace_sampled = headers.get("x-b3-sampled")
        self.span_id = None
        self.trace_id = None
        self.trace_sampled = False
        trace_context = headers.get("x-cloud-trace-context")
        self.trace = trace_context
        if trace_context and len(trace_context) > 0:
            parts = trace_context.split("/")
            self.trace_id = parts[0]
            if len(parts) > 1:
                self.span_id = parts[1].split(";")[0]
                self.trace_sampled = parts[1].split(";")[1] == "o=1" if len(parts[1].split(";")) > 1 else False
        # auth header is used for local development
        self.user_id = headers.get("x-goog-authenticated-user-id")
        self.user_email = headers.get("x-goog-authenticated-user-email")
        if not self.iap_jwt_assertion and headers.get("authorization"):
            self.iap_jwt_assertion = self.decode_jwt(headers.get("authorization"))
            if self.iap_jwt_assertion:
                self.user_id = self.iap_jwt_assertion.get("user_id")
                self.user_email = self.iap_jwt_assertion.get("email")

    def __repr__(self) -> str:
        # Omitting sensitive data like email and jwt assertion
        safe_properties = dict(
            user_id=self.user_id, client_user_agent=self.client_user_agent, client_host=self.client_host
        )
        return f"request-context={safe_properties})"


def get_request_context():
    return _request_context.get()
