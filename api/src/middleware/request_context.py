import base64
import hashlib
import hmac
import json
import logging
from contextvars import ContextVar

import requests
from google.auth import jwt
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
                if not self.google_public_keys:
                    logging.error("Fetched Google's public keys, but the result is empty or invalid.")
            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to fetch Google's public keys: {e}")

    def decode_jwt(self, token: str):
        """
        :param token: jwt token
        :return:
        This method decodes a JWT token using Google's public keys.
        No exception is raised if the token is invalid, None is returned instead.
        """
        try:
            token = token.replace("Bearer ", "")
            self.resolve_google_public_keys()
            if not self.google_public_keys:
                logging.error("Cannot decode JWT: Google's public keys are not available.")
                return None
            return jwt.decode(token, self.google_public_keys, audience=get_config(PROJECT_ID))
        except Exception as e:
            logging.error("Error decoding JWT: %s", e)
            return None

    def decode_user_context_jwt(self, token: str):
        """Decode and verify the custom user-context JWT sent by the web app.

        This token is signed with HS256 using a shared secret (S2S_JWT_SECRET).
        If verification fails for any reason, None is returned and the request
        falls back to the existing IAP / Authorization-based identity handling.
        """
        try:
            secret = get_config("S2S_JWT_SECRET")
            if not secret or len(secret) < 32:
                # Misconfiguration: do not fail the request, just skip user-context.
                logging.error(
                    "S2S_JWT_SECRET is missing or too short; " "cannot verify x-mdb-user-context token.",
                )
                return None

            token = token.replace("Bearer ", "")
            parts = token.split(".")
            if len(parts) != 3:
                return None

            header_b64, payload_b64, signature_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

            expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()

            # JWT uses URL-safe base64 without padding
            def b64url_decode(value: str) -> bytes:
                padding = "=" * (-len(value) % 4)
                return base64.urlsafe_b64decode(value + padding)

            actual_sig = b64url_decode(signature_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                logging.warning("Invalid signature for x-mdb-user-context token")
                return None

            payload_json = b64url_decode(payload_b64).decode("utf-8")
            payload = json.loads(payload_json)
            # Minimal shape we care about: { uid, email?, isGuest? }
            if not isinstance(payload, dict) or "uid" not in payload:
                return None
            return payload
        except Exception as e:  # pragma: no cover - defensive
            logging.error("Error decoding user-context JWT: %s", e)
            return None

    def _extract_from_headers(self, headers: dict, scope: Scope) -> None:
        self.host = headers.get("host")
        self.protocol = headers.get("x-forwarded-proto") if headers.get("x-forwarded-proto") else scope.get("scheme")
        self.client_host = headers.get("x-forwarded-for")
        self.server_ip = scope.get("server")[0] if scope.get("server") and len(scope.get("server")) > 0 else ""
        if not self.client_host:
            self.client_host = scope.get("client")[0] if scope.get("client") and len(scope.get("client")) > 0 else ""
        else:
            # X-Forwarded-For: client, proxy1, proxy2
            forwarded_ips = self.client_host.split(",")
            self.client_host = (
                str(forwarded_ips[0]).strip() if len(forwarded_ips) > 0 else str(self.client_host).strip()
            )
            # merge all forwarded ips but the first one
            self.server_ip = ",".join(forwarded_ips[1:]).strip() if len(forwarded_ips) > 1 else self.server_ip
        self.client_user_agent = headers.get("user-agent")
        self.iap_jwt_assertion = headers.get("x-goog-iap-jwt-assertion")
        self.span_id = None
        self.trace_id = None
        self.trace_sampled = False
        trace_context = headers.get("x-cloud-trace-context")
        self.trace = trace_context
        # x-cloud-trace-context: TRACE_ID/SPAN_ID;o=TRACE_TRUE
        if trace_context and len(trace_context) > 0:
            parts = trace_context.split("/")
            self.trace_id = parts[0]
            if len(parts) > 1:
                self.span_id = parts[1].split(";")[0]
                self.trace_sampled = parts[1].split(";")[1] == "o=1" if len(parts[1].split(";")) > 1 else False
        # auth header is used for local development
        self.user_id = headers.get("x-goog-authenticated-user-id")
        self.user_email = headers.get("x-goog-authenticated-user-email")
        self.is_guest = False
        self.google_public_keys = None
        if not self.iap_jwt_assertion and headers.get("authorization"):
            self.iap_jwt_assertion = self.decode_jwt(headers.get("authorization"))
            if self.iap_jwt_assertion:
                self.user_id = self.iap_jwt_assertion.get("user_id")
                self.user_email = self.iap_jwt_assertion.get("email")

        # Optional user-context header set by the web app for server-to-server calls.
        # Name is aligned with the frontend's USER_CONTEXT_HEADER.
        user_context_header = headers.get("x-mdb-user-context") or headers.get("md-user-context")
        if user_context_header:
            user_context = self.decode_user_context_jwt(user_context_header)
            if user_context:
                # Prefer values from the verified user-context token when present.
                self.user_id = user_context.get("uid", self.user_id)
                self.user_email = user_context.get("email", self.user_email)
                self.is_guest = bool(user_context.get("isGuest"))

    def __repr__(self) -> str:
        # Omitting sensitive data like email and jwt assertion
        safe_properties = dict(
            user_id=self.user_id,
            client_user_agent=self.client_user_agent,
            client_host=self.client_host,
            email=self.user_email,
        )
        return f"request-context={safe_properties})"


def get_request_context():
    return _request_context.get()


def is_user_email_restricted() -> bool:
    """
    Check if an email's domain is restricted (e.g., for WIP visibility).
    """
    request_context = get_request_context()
    if not request_context:
        return True
    email = request_context["user_email"]
    unrestricted_domains = ["mobilitydata.org"]
    return not email or not any(email.endswith(f"@{domain}") for domain in unrestricted_domains)
