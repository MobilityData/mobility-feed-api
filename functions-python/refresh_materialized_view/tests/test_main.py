import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from main import refresh_materialized_view_function  # noqa: E402


class TestRefreshMaterializedView:
    """Test class for the refresh materialized view function."""

    @patch("main.refresh_materialized_view")
    def test_refresh_view_success(self, mock_refresh):
        """Test successful view refresh."""
        mock_refresh.return_value = True

        # Mock request object
        request = Mock()
        request.method = "GET"

        # Mock database session
        db_session = Mock()

        # Call the function
        response, status_code = refresh_materialized_view_function(request, db_session)

        # Assertions
        assert "Successfully refreshed materialized view" in response["message"]
        mock_refresh.assert_called_once_with(db_session, "my_materialized_view")

    @patch("main.refresh_materialized_view")
    def test_refresh_view_failure(self, mock_refresh):
        """Test failure to refresh the view."""
        mock_refresh.return_value = False

        # Mock request object
        request = Mock()
        request.method = "GET"

        # Mock database session
        db_session = Mock()

        # Call the function
        response, status_code = refresh_materialized_view_function(request, db_session)

        # Assertions
        assert status_code == 500
        assert "Failed to refresh materialized view" in response["error"]
        mock_refresh.assert_called_once_with(db_session, "my_materialized_view")

    @patch("main.refresh_materialized_view")
    def test_refresh_view_exception(self, mock_refresh):
        """Test exception during view refresh."""
        mock_refresh.side_effect = Exception("Database connection failed")

        # Mock request object
        request = Mock()
        request.method = "GET"

        # Mock database session
        db_session = Mock()

        # Call the function
        response, status_code = refresh_materialized_view_function(request, db_session)

        # Assertions
        assert status_code == 500
        assert "Error refreshing materialized view" in response["error"]
        assert "Database connection failed" in response["error"]
        mock_refresh.assert_called_once_with(db_session, "my_materialized_view")


if __name__ == "__main__":
    pytest.main([__file__])
