import pytest
from fastapi import HTTPException

from conftest import feed_mdb_40
from feeds_operations.impl.feeds_operations_impl import OperationsApiImpl
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import ConfigKey, ConfigValueFeed, Feed
from shared.helpers.utils import default_request_headers
from test_shared.test_utils.database_utils import default_db_url

BUILT_IN = default_request_headers(feed_mdb_40.producer_url)


@with_db_session(db_url=default_db_url)
def _set_key(default_value=None, override=None, db_session=None):
    db_session.query(ConfigValueFeed).delete()
    db_session.query(ConfigKey).delete()
    db_session.add(
        ConfigKey(
            namespace="feed_download", key="http_headers", default_value=default_value
        )
    )
    if override is not None:
        db_session.add(
            ConfigValueFeed(
                feed_id=feed_mdb_40.id,
                feed_stable_id=feed_mdb_40.stable_id,
                namespace="feed_download",
                key="http_headers",
                value=override,
            )
        )
    db_session.commit()


@with_db_session(db_url=default_db_url)
def _clear(db_session=None):
    db_session.query(ConfigValueFeed).delete()
    db_session.query(ConfigKey).delete()
    db_session.commit()


@with_db_session(db_url=default_db_url)
def _set_auth(authentication_type, db_session=None):
    db_session.query(Feed).filter(Feed.id == feed_mdb_40.id).update(
        {"authentication_type": authentication_type}
    )
    db_session.commit()


@pytest.fixture(autouse=True)
def clean_config():
    _clear()
    yield
    _clear()
    _set_auth(feed_mdb_40.authentication_type)


def _headers():
    return OperationsApiImpl().get_gtfs_feed_download_headers(id=feed_mdb_40.stable_id)


def test_built_in_headers_when_nothing_is_set():
    _set_key()
    response = _headers()
    assert response.feed_id == feed_mdb_40.stable_id
    assert response.source == "built_in"
    assert response.headers == BUILT_IN
    assert response.built_in_headers == BUILT_IN
    assert response.built_in_headers["Referer"] == feed_mdb_40.producer_url


def test_override_headers():
    _set_key(override={"User-Agent": "curl/8.0"})
    response = _headers()
    assert response.source == "override"
    assert response.headers == {"User-Agent": "curl/8.0"}
    assert response.built_in_headers == BUILT_IN


def test_key_default_is_reported_as_sent():
    # An empty default replaces the built-in headers in the download; show it as is.
    _set_key(default_value={})
    response = _headers()
    assert response.source == "config_default"
    assert response.headers == {}
    assert response.built_in_headers == BUILT_IN


def test_api_key_header_named_only_for_header_auth():
    _set_key()
    assert _headers().api_key_header is None
    _set_auth("2")
    response = _headers()
    assert response.api_key_header == feed_mdb_40.api_key_parameter_name
    assert feed_mdb_40.api_key_parameter_name not in response.headers


def test_unknown_feed():
    with pytest.raises(HTTPException) as exc:
        OperationsApiImpl().get_gtfs_feed_download_headers(id="mdb-missing")
    assert exc.value.status_code == 404
