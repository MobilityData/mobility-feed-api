# coding: utf-8

from fastapi.testclient import TestClient


from feeds_gen.models.search_feeds200_response import SearchFeeds200Response  # noqa: F401


def test_search_feeds(client: TestClient):
    """Test case for search_feeds

    
    """
    params = [("limit", 10),     ("offset", 0),     ("status", 'status_example'),     ("feed_id", 'mdb-1210'),     ("data_type", 'gtfs'),     ("search_query", 'search_query_example')]
    headers = {
        "Authentication": "special-key",
    }
    response = client.request(
        "GET",
        "/v1/search",
        headers=headers,
        params=params,
    )

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

