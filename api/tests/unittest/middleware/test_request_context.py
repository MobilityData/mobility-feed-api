import unittest
from unittest.mock import MagicMock

import pytest
from starlette.datastructures import Headers

from middleware.request_context import RequestContext, get_request_context, _request_context


class TestRequestContext(unittest.TestCase):
    def test_init_extract_headers(self):
        scope_instance = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "headers": [
                (b"host", b"localhost"),
                (b"x-forwarded-proto", b"https"),
                (b"x-forwarded-for", b"client, proxy1"),
                (b"server", b"server"),
                (b"user-agent", b"user-agent"),
                (b"x-goog-iap-jwt-assertion", b"jwt"),
                (b"x-cloud-trace-context", b"TRACE_ID/SPAN_ID;o=1"),
                (b"x-goog-authenticated-user-id", b"user_id"),
                (b"x-goog-authenticated-user-email", b"email"),
            ],
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "client": ("127.0.0.1", 32767),
            "server": ("127.0.0.1", 80),
        }
        request_context = RequestContext(scope=scope_instance)
        expected = {
            "client_host": "client",
            "client_user_agent": "user-agent",
            "google_public_keys": None,
            "is_guest": False,
            "headers": Headers(scope=scope_instance),
            "host": "localhost",
            "iap_jwt_assertion": "jwt",
            "protocol": "https",
            "scope": scope_instance,
            "server_ip": "proxy1",
            "span_id": "SPAN_ID",
            "trace": "TRACE_ID/SPAN_ID;o=1",
            "trace_id": "TRACE_ID",
            "trace_sampled": True,
            "user_email": "email",
            "user_id": "user_id",
        }
        self.assertEqual(expected, request_context.__dict__)

    def test_get_request_context(self):
        request_context = RequestContext(MagicMock())
        _request_context.set(request_context)
        self.assertEqual(request_context, get_request_context())


@pytest.mark.parametrize(
    "raw_user_id, expected",
    [
        (None, None),
        ("plainuserid", "plainuserid"),
        ("accounts.google.com:1234567890", "1234567890"),
        ("prefix:middle:finalpart", "finalpart"),
    ],
)
def test_extract_user_id_parametrized(raw_user_id, expected):
    assert RequestContext.extract_user_id(raw_user_id) == expected
