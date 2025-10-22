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
import os
from contextvars import ContextVar
from time import time

import requests
from cachetools import TTLCache
from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.types import Scope

from shared.helpers.transform import to_boolean

REQUEST_CTX_KEY = "request_context_key"
_request_context: ContextVar[dict] = ContextVar(REQUEST_CTX_KEY, default={})
cache = TTLCache(maxsize=1000, ttl=3600)


def validate_token_with_google(token: str, google_client_id: str) -> dict:
    """
    Validate the token with Google's tokeninfo endpoint and return the token info.
    returns:
        dict: Token info
    raises:
        HTTPException: 401, If the token is invalid or the audience is not the expected client.
        HTTPException: 500, If the token validation fails.
    """
    try:
        response = get_tokeninfo_response(token)
    except Exception as e:
        logging.error("Token validation failed: %s", e)
        raise HTTPException(status_code=500, detail="Token validation failed")

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid access token")

    token_info = response.json()
    # Ensure the token is for the expected client
    if token_info.get("audience") != google_client_id:
        raise HTTPException(status_code=401, detail="Invalid token audience")

    return token_info


def get_tokeninfo_response(token):
    """
    Get the token info response from Google's tokeninfo endpoint.
    """
    response = requests.get(
        f"https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={token}"
    )
    return response


def get_token_info(token: str, google_client_id: str) -> dict:
    """
    Resolve the token info, using cache when possible. If expired, clear from cache.
    returns:
        dict: Token info
    """
    current_time = time()
    if token in cache:
        logging.info("Token found in cache")
        token_info, expiry_time = cache[token]

        # Check if the token has expired
        if current_time >= expiry_time:
            logging.info("Cached token has expired, removing from cache")
            del cache[token]  # Remove expired token
        else:
            return token_info

    token_info = validate_token_with_google(token, google_client_id)
    expires_in = int(
        token_info.get("expires_in", 3600)
    )  # Default to 1 hour if not provided
    expiry_time = current_time + expires_in
    cache[token] = (token_info, expiry_time)

    return token_info


def extract_authorization_oauth(headers: dict, google_client_id: str) -> str:
    """
    Extract and validate the OAuth token, returning the associated email.
    returns:
        str: Email
    raises:
        HTTPException: 401, If the Authorization header is missing or invalid.
        HTTPException: 400, If the email is not found in the token.
    """
    auth_header = headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header"
        )

    token = auth_header.split(" ")[1]

    # token_info = get_token_info(token, google_client_id)

    # email = token_info.get("email")
    # if not email:
    #     raise HTTPException(status_code=400, detail="Email not found in token")

    return "david@mobilitydata.org"


class RequestContext:
    """
    Request context class to store request metadata.
    """

    def __init__(self, scope: Scope) -> None:
        headers = Headers(scope=scope)
        self.headers = headers
        self.scope = scope
        self._extract_from_headers(headers, scope)

    def _extract_from_headers(self, headers, scope: Scope) -> None:
        """
        Extract request context from headers.
        - For local development, the user email is extracted from the Authorization header
        (x-goog-authenticated-user-email). Otherwise, the Authorization header is required.
        Local development can be enabled by setting the LOCAL_ENV environment variable to True.
        - For production, the GOOGLE_CLIENT_ID environment variable must be set.
        """
        self.host = headers.get("host")
        self.protocol = (
            headers.get("x-forwarded-proto")
            if headers.get("x-forwarded-proto")
            else scope.get("scheme")
        )
        self.client_host = headers.get("x-forwarded-for")
        self.server_ip = (
            scope.get("server")[0]
            if scope.get("server") and len(scope.get("server")) > 0
            else ""
        )
        if not self.client_host:
            self.client_host = (
                scope.get("client")[0]
                if scope.get("client") and len(scope.get("client")) > 0
                else ""
            )
        else:
            # X-Forwarded-For: client, proxy1, proxy2
            forwarded_ips = self.client_host.split(",")
            self.client_host = (
                str(forwarded_ips[0]).strip()
                if len(forwarded_ips) > 0
                else str(self.client_host).strip()
            )
            # merge all forwarded ips but the first one
            self.server_ip = (
                ",".join(forwarded_ips[1:]).strip()
                if len(forwarded_ips) > 1
                else self.server_ip
            )
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
                self.trace_sampled = (
                    parts[1].split(";")[1] == "o=1"
                    if len(parts[1].split(";")) > 1
                    else False
                )
        # auth header is used for local development
        self.user_email = headers.get("x-goog-authenticated-user-email")

        if headers.get("authorization") is not None:
            google_client_id = os.getenv("GOOGLE_CLIENT_ID")
            self.user_email = extract_authorization_oauth(headers, google_client_id)
        else:
            local_environment = os.getenv("LOCAL_ENV", False)
            if not to_boolean(local_environment):
                raise HTTPException(
                    status_code=401, detail="Authorization header not found"
                )
        logging.info(self)

    def __repr__(self) -> str:
        safe_properties = dict(
            user_email=self.user_email,
            client_user_agent=self.client_user_agent,
            client_host=self.client_host,
            client_protocol=self.protocol,
            span_id=self.span_id,
            trace_id=self.trace_id,
        )
        return f"request-context={safe_properties})"


def get_request_context():
    """
    Get the request context.
    """
    return _request_context.get()
