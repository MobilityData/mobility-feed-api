# coding: utf-8

from fastapi.testclient import TestClient


from feeds_gen.models.search_entities200_response import SearchEntities200Response  # noqa: F401


def test_search_entities(client: TestClient):
    """Test case for search_entities

    
    """
    params = [("limit", 10),     ("offset", 0)]
    headers = {
        "Authorization": "Bearer special-key",
    }
    response = client.request(
        "GET",
        "/v1/search",
        headers=headers,
        params=params,
    )

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

