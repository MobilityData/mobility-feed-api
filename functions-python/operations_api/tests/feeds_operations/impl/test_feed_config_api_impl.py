import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from jsonschema.validators import validator_for

from conftest import feed_mdb_40, feed_mdb_41
from feeds_gen.apis.config_api import router
from feeds_gen.models.extra_models import TokenModel
from feeds_gen.models.feed_config_entry import FeedConfigEntry
from feeds_gen.models.set_feed_config_value_request import SetFeedConfigValueRequest
from feeds_gen.security_api import get_token_ApiKeyAuth
from feeds_operations.impl.config_value_schemas import VALUE_SCHEMAS
from feeds_operations.impl.feed_config_api_impl import FeedConfigApiImpl
from middleware.request_context_oauth2 import _request_context
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import ConfigKey, ConfigValueFeed
from test_shared.test_utils.database_utils import default_db_url

OPERATOR = "operator@example.com"


@with_db_session(db_url=default_db_url)
def _seed(db_session=None):
    db_session.add_all(
        [
            ConfigKey(
                namespace="feed_download",
                key="http_headers",
                description="HTTP headers",
            ),
            ConfigKey(namespace="parquet_builder", key="size"),
            ConfigKey(namespace="reverse_geolocation", key="any", default_value=3),
        ]
    )
    db_session.commit()


@with_db_session(db_url=default_db_url)
def _clear(db_session=None):
    db_session.query(ConfigValueFeed).delete()
    db_session.query(ConfigKey).delete()
    db_session.commit()


@pytest.fixture(autouse=True)
def config_keys():
    _clear()
    _seed()
    token = _request_context.set({"user_email": OPERATOR})
    yield
    _request_context.reset(token)
    _clear()


def _put(value, key=("feed_download", "http_headers"), feed=feed_mdb_40, **kwargs):
    return FeedConfigApiImpl().set_feed_config_value(
        id=feed.stable_id,
        namespace=key[0],
        key=key[1],
        set_feed_config_value_request=SetFeedConfigValueRequest(value=value, **kwargs),
    )


def _entry(feed=feed_mdb_40, key=("feed_download", "http_headers")) -> FeedConfigEntry:
    entries = FeedConfigApiImpl().get_feed_config(id=feed.stable_id)
    return next(e for e in entries if (e.namespace, e.key) == key)


def _error(fn, *args, **kwargs) -> HTTPException:
    with pytest.raises(HTTPException) as exc:
        fn(*args, **kwargs)
    return exc.value


@pytest.mark.parametrize("key, schema", VALUE_SCHEMAS.items())
def test_value_schemas_are_valid(key, schema):
    validator_for(schema).check_schema(schema)


def test_list_config_keys_ordered_with_schema():
    keys = FeedConfigApiImpl().list_config_keys()
    assert [(k.namespace, k.key) for k in keys] == [
        ("feed_download", "http_headers"),
        ("parquet_builder", "size"),
        ("reverse_geolocation", "any"),
    ]
    assert keys[0].value_schema["maxProperties"] == 50
    assert keys[2].default_value == 3


def test_get_feed_config_without_overrides():
    entries = FeedConfigApiImpl().get_feed_config(id=feed_mdb_40.stable_id)
    by_key = {(e.namespace, e.key): e for e in entries}
    headers = by_key[("feed_download", "http_headers")]
    assert headers.source == "none"
    assert headers.override is None and headers.effective_value is None
    default = by_key[("reverse_geolocation", "any")]
    assert default.source == "default"
    assert default.effective_value == 3


def test_get_feed_config_unknown_feed():
    error = _error(FeedConfigApiImpl().get_feed_config, id="mdb-does-not-exist")
    assert error.status_code == 404


def test_put_creates_then_replaces():
    created = _put({"User-Agent": "MobilityDatabaseAgent"})
    assert created.status_code == 201
    body = json.loads(created.body)
    assert body["source"] == "override"
    assert body["updated_by"] == OPERATOR

    replaced = _put({"User-Agent": "curl/8.0", "Accept": "*/*"})
    assert isinstance(replaced, FeedConfigEntry)
    assert replaced.override == {"User-Agent": "curl/8.0", "Accept": "*/*"}
    assert replaced.effective_value == replaced.override

    entry = _entry()
    assert entry.source == "override"
    assert entry.updated_by == OPERATOR
    assert entry.updated_at == replaced.updated_at


def test_put_is_per_feed_and_works_for_any_feed_type():
    _put({"Accept": "*/*"}, feed=feed_mdb_41)
    assert _entry(feed=feed_mdb_41).source == "override"
    assert _entry(feed=feed_mdb_40).source == "none"


def test_put_overrides_a_default():
    _put(7, key=("reverse_geolocation", "any"))
    entry = _entry(key=("reverse_geolocation", "any"))
    assert (entry.source, entry.effective_value, entry.default_value) == (
        "override",
        7,
        3,
    )


def test_key_without_schema_accepts_any_json():
    _put({"anything": [1, "two"]}, key=("reverse_geolocation", "any"))
    assert _entry(key=("reverse_geolocation", "any")).value_schema is None


def test_put_unknown_key_or_feed():
    assert _error(_put, 1, key=("nope", "nope")).status_code == 404
    feed = type("F", (), {"stable_id": "mdb-does-not-exist"})
    assert _error(_put, {"Accept": "*/*"}, feed=feed).status_code == 404


def test_put_null_value_refused():
    assert _error(_put, None, key=("reverse_geolocation", "any")).status_code == 422


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "Bearer x"},
        {"authorization": "Bearer x"},
        {"Cookie": "a=b"},
        {"X-Api-Key": "k"},
        {"Proxy-Authorization": "x"},
    ],
)
def test_headers_credentials_refused(headers):
    error = _error(_put, headers)
    assert error.status_code == 422
    assert "is not allowed" in error.detail


@pytest.mark.parametrize(
    "headers",
    [
        {"Bad Name": "x"},
        {"User-Agent": "line\nbreak"},
        {"User-Agent": 5},
        {f"X-H{i}": "v" for i in range(51)},
        ["User-Agent"],
    ],
)
def test_headers_invalid_shape_refused(headers):
    assert _error(_put, headers).status_code == 422


def test_headers_allowed_names():
    # The token rule allows the quote in the migration's escaped pattern.
    _put({"X-It's": "ok", "Referer": "https://example.com/feed.zip"})
    assert _entry().override["X-It's"] == "ok"


@pytest.mark.parametrize("value", ["s", "m", "l", {"size": "l", "locked": True}])
def test_parquet_size_accepted(value):
    _put(value, key=("parquet_builder", "size"))
    assert _entry(key=("parquet_builder", "size")).override == value


@pytest.mark.parametrize(
    "value",
    ["xl", {"locked": True}, {"size": "m", "locked": "yes"}, {"size": "m", "x": 1}],
)
def test_parquet_size_refused(value):
    assert _error(_put, value, key=("parquet_builder", "size")).status_code == 422


def test_expected_updated_at():
    _put({"Accept": "*/*"})
    current = _entry().updated_at

    stale = current - timedelta(seconds=1)
    assert _error(_put, {"A": "b"}, expected_updated_at=stale).status_code == 409
    assert _entry().override == {"Accept": "*/*"}

    _put({"A": "b"}, expected_updated_at=current)
    assert _entry().override == {"A": "b"}


def test_expected_updated_at_without_override_conflicts():
    read_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert _error(_put, {"A": "b"}, expected_updated_at=read_at).status_code == 409


def test_delete():
    _put(7, key=("reverse_geolocation", "any"))
    api = FeedConfigApiImpl()
    response = api.delete_feed_config_value(
        id=feed_mdb_40.stable_id, namespace="reverse_geolocation", key="any"
    )
    assert response.status_code == 204
    entry = _entry(key=("reverse_geolocation", "any"))
    assert (entry.source, entry.effective_value) == ("default", 3)

    error = _error(
        api.delete_feed_config_value,
        id=feed_mdb_40.stable_id,
        namespace="reverse_geolocation",
        key="any",
    )
    assert error.status_code == 404


def test_delete_expected_updated_at():
    _put({"Accept": "*/*"})
    current = _entry().updated_at
    api = FeedConfigApiImpl()
    kwargs = dict(
        id=feed_mdb_40.stable_id, namespace="feed_download", key="http_headers"
    )

    stale = (current - timedelta(seconds=1)).isoformat()
    assert (
        _error(
            api.delete_feed_config_value, expected_updated_at=stale, **kwargs
        ).status_code
        == 409
    )
    bad = _error(
        api.delete_feed_config_value, expected_updated_at="yesterday", **kwargs
    )
    assert bad.status_code == 422

    response = api.delete_feed_config_value(
        expected_updated_at=current.isoformat(), **kwargs
    )
    assert response.status_code == 204


def test_http_status_codes():
    """The generated routes pass the impl's 201 and 204 through instead of a 200."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_token_ApiKeyAuth] = lambda: TokenModel(sub="test")
    client = TestClient(app)
    url = f"/v1/operations/feeds/{feed_mdb_40.stable_id}/config/feed_download/http_headers"

    created = client.put(url, json={"value": {"Accept": "*/*"}})
    assert created.status_code == 201
    replaced = client.put(
        url,
        json={"value": {"A": "b"}, "expected_updated_at": created.json()["updated_at"]},
    )
    assert replaced.status_code == 200
    assert client.get(f"/v1/operations/feeds/{feed_mdb_40.stable_id}/config").json()[0][
        "override"
    ] == {"A": "b"}
    assert client.delete(url).status_code == 204
    assert client.get("/v1/operations/config/keys").status_code == 200
