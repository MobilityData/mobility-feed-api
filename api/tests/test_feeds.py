from fastapi.testclient import TestClient
from pytest_mock import mocker
from sqlalchemy.sql import Select
from database.database import DB_ENGINE
from database_gen.sqlacodegen_models import Feed, Externalid, t_redirectingid


def test_feeds_get(client: TestClient, mocker):
    """
    Unit test for get_feeds
    """
    mock_select = mocker.patch.object(DB_ENGINE, 'select')
    def mock_select_side_effect(model=None, query=None, conditions=None, attributes=None, update_session=True, limit=None, offset=None):
        if isinstance(query, Select):
            mock_feed = Feed(stable_id="test_id")
            mock_feed.target_ids = "test_target_id"
            mock_feed.associated_ids = "test_associated_id"
            mock_feed.sources = "test_source"
            return [mock_feed]
        return []
    mock_select.side_effect = mock_select_side_effect
    response = client.request(
        "GET",
        "/v1/feeds",
    )

    assert mock_select.call_count == 1, f'select() was called {mock_select.call_count} times instead of 3 times'
    assert response.status_code == 200, f'Response status code was {response.status_code} instead of 200'
    response_feed = response.json()[0]
    assert response_feed["id"] == "test_id", f'Response feed id was {response_feed.id} instead of test_id'
    assert response_feed["external_ids"][0]["external_id"] == "test_associated_id", f'Response feed external id was {response_feed["external_ids"][0]["external_id"]} instead of test_associated_id'
    assert response_feed["external_ids"][0]["source"] == "test_source", f'Response feed source was {response_feed["external_ids"][0]["source"]} instead of test_source'
    assert response_feed["redirects"][0] == "test_target_id", f'Response feed redirect was {response_feed["redirects"][0]} instead of test_target_id'

def test_feed_get(client: TestClient, mocker):
    """
    Unit test for get_feeds
    """
    mock_select = mocker.patch.object(DB_ENGINE, 'select')
    def mock_select_side_effect(model=None, query=None, conditions=None, attributes=None, update_session=True, limit=None, offset=None):
        if isinstance(query, Select):
            mock_feed = Feed(stable_id="test_id")
            mock_feed.target_ids = "test_target_id"
            mock_feed.associated_ids = "test_associated_id"
            mock_feed.sources = "test_source"
            return [mock_feed]
        return []
    mock_select.side_effect = mock_select_side_effect
    response = client.request(
        "GET",
        "/v1/feeds/test_id",
    )

    assert mock_select.call_count == 1, f'select() was called {mock_select.call_count} times instead of 3 times'
    assert response.status_code == 200, f'Response status code was {response.status_code} instead of 200'
    response_feed = response.json()
    assert response_feed["id"] == "test_id", f'Response feed id was {response_feed.id} instead of test_id'
    assert response_feed["external_ids"][0]["external_id"] == "test_associated_id", f'Response feed external id was {response_feed["external_ids"][0]["external_id"]} instead of test_associated_id'
    assert response_feed["external_ids"][0]["source"] == "test_source", f'Response feed source was {response_feed["external_ids"][0]["source"]} instead of test_source'
    assert response_feed["redirects"][0] == "test_target_id", f'Response feed redirect was {response_feed["redirects"][0]} instead of test_target_id'
