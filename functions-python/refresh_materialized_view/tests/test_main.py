import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


@pytest.fixture
def mock_environment_variables(monkeypatch):
    monkeypatch.setenv("PROJECT_ID", "test-project")
    monkeypatch.setenv("QUEUE_NAME", "test-queue")
    monkeypatch.setenv("LOCATION", "us-central1")
    monkeypatch.setenv("FUNCTION_URL", "http://localhost")


@pytest.fixture
def mock_cloud_tasks_client(mocker):
    mock_client = mocker.Mock()
    mocker.patch("src.main.tasks_v2.CloudTasksClient", return_value=mock_client)
    return mock_client


@pytest.mark.parametrize("endpoint", ["/refresh-materialized-view"])
def test_refresh_materialized_view_function(endpoint):
    response = client.post(endpoint, json={})
    assert response.status_code == 200
    assert "Task" in response.json()["message"]


@pytest.mark.parametrize("endpoint", ["/refresh-materialized-view-task"])
def test_refresh_materialized_view_task(endpoint):
    payload = {"view_name": "test_view", "deduplication_key": "test_key"}
    response = client.post(endpoint, json=payload)
    assert response.status_code == 200
    assert "Successfully refreshed materialized view" in response.json()["message"]
