from unittest.mock import patch
from tasks.refresh_feedsearch_view import refresh_materialized_view


def test_refresh_materialized_view_handler_dry_run():
    payload = {"dry_run": True}
    with patch("tasks.refresh_feedsearch_view.get_parameters", return_value=True):
        resp, status = refresh_materialized_view.refresh_materialized_view_handler(
            payload
        )
        assert status == 200
        assert resp["dry_run"] is True
        assert "Dry run" in resp["message"]


@patch("tasks.refresh_feedsearch_view.refresh_materialized_view")
def test_refresh_materialized_view_handler_success(mock_refresh):
    payload = {"dry_run": False}
    mock_refresh.return_value = True
    with patch("tasks.refresh_feedsearch_view.get_parameters", return_value=False):
        resp, status = refresh_materialized_view.refresh_materialized_view_handler(
            payload
        )
        assert status == 200
        assert "Successfully refreshed" in resp["message"]
