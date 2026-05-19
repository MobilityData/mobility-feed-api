"""
Unit tests for the search_feeds MCP tool.
Tests use mocking to avoid requiring a live database.
"""
import json
import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

import pytest

# We need to mock shared modules before importing the tool since the
# shared/ symlinks may not exist in the test environment.
# Create mock modules for all shared dependencies.
mock_database_module = MagicMock()
mock_database_class = MagicMock()
mock_db_instance = MagicMock()
mock_database_class.return_value = mock_db_instance
mock_database_module.Database = mock_database_class

mock_unaccent_module = MagicMock()
mock_unaccent = MagicMock(side_effect=lambda x: x)
mock_unaccent_module.unaccent = mock_unaccent

mock_models_module = MagicMock()

# Patch sys.modules before importing anything from the tools package
sys.modules['shared'] = MagicMock()
sys.modules['shared.database'] = MagicMock()
sys.modules['shared.database.database'] = mock_database_module
sys.modules['shared.database.sql_functions'] = MagicMock()
sys.modules['shared.database.sql_functions.unaccent'] = mock_unaccent_module
sys.modules['shared.database_gen'] = MagicMock()
sys.modules['shared.database_gen.sqlacodegen_models'] = mock_models_module

# Add mcp/src to path so we can import tools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def _make_mock_col(name):
    """Create a MagicMock that properly exposes .name as an attribute."""
    col = MagicMock()
    col.name = name
    return col


_UNSET = object()


def make_feed_row(
    feed_stable_id="mdb-1",
    provider="Test Provider",
    feed_name="Test Feed",
    data_type="gtfs",
    status="active",
    official=True,
    locations=_UNSET,
    latest_dataset_id="mdb-1-202401010000",
    latest_dataset_hosted_url="https://example.com/feed.zip",
    latest_dataset_downloaded_at=None,
    latest_dataset_service_date_range_start=None,
    latest_dataset_service_date_range_end=None,
    latest_total_error=0,
    latest_total_warning=2,
    latest_total_info=1,
    latest_dataset_features=_UNSET,
    rank=0.75,
):
    """Create a mock database row."""
    row = MagicMock()
    row._mapping = {
        "feed_stable_id": feed_stable_id,
        "provider": provider,
        "feed_name": feed_name,
        "data_type": data_type,
        "status": status,
        "official": official,
        "locations": locations if locations is not _UNSET else [{"country_code": "CA", "country": "Canada", "subdivision_name": "Quebec", "municipality": "Montreal"}],
        "latest_dataset_id": latest_dataset_id,
        "latest_dataset_hosted_url": latest_dataset_hosted_url,
        "latest_dataset_downloaded_at": latest_dataset_downloaded_at,
        "latest_dataset_service_date_range_start": latest_dataset_service_date_range_start,
        "latest_dataset_service_date_range_end": latest_dataset_service_date_range_end,
        "latest_total_error": latest_total_error,
        "latest_total_warning": latest_total_warning,
        "latest_total_info": latest_total_info,
        "latest_dataset_features": latest_dataset_features if latest_dataset_features is not _UNSET else ["Shapes", "Headsigns"],
        "rank": rank,
    }
    return row


class TestSearchFeedsTool:
    """Tests for the search_feeds_tool function."""

    def setup_method(self):
        """Set up mocks for each test."""
        mock_models_module.t_feedsearch = MagicMock()
        mock_models_module.t_feedsearch.columns = [
            _make_mock_col("feed_stable_id"),
            _make_mock_col("provider"),
            _make_mock_col("feed_name"),
            _make_mock_col("data_type"),
            _make_mock_col("status"),
            _make_mock_col("official"),
            _make_mock_col("locations"),
            _make_mock_col("document"),  # excluded from feed_search_columns
        ]

        # Set up context manager for db session
        self.mock_session = MagicMock()
        mock_db_instance.start_db_session.return_value.__enter__ = MagicMock(return_value=self.mock_session)
        mock_db_instance.start_db_session.return_value.__exit__ = MagicMock(return_value=False)

    def _call_tool(self, search_query="Montreal", **kwargs):
        """Import and call the tool fresh (needed due to module-level setup).

        SQLAlchemy is mocked so that select()/func/or_ don't validate column
        types — the session.execute() is already mocked, so we only need the
        query-builder calls to return chainable MagicMocks.
        """
        if 'tools.search_feeds' in sys.modules:
            del sys.modules['tools.search_feeds']
        if 'tools' in sys.modules:
            del sys.modules['tools']

        mock_sa = MagicMock()
        with patch.dict(sys.modules, {'sqlalchemy': mock_sa}):
            from tools.search_feeds import search_feeds_tool
            return search_feeds_tool(search_query=search_query, **kwargs)

    def test_returns_valid_json(self):
        """Tool always returns valid JSON."""
        self.mock_session.execute.return_value.fetchall.return_value = []
        self.mock_session.execute.return_value.fetchone.return_value = (0,)
        result = self._call_tool("Montreal")
        parsed = json.loads(result)
        assert "query" in parsed
        assert "total_matches" in parsed
        assert "results" in parsed

    def test_query_echoed_in_output(self):
        """The search_query is reflected in the output."""
        self.mock_session.execute.return_value.fetchall.return_value = []
        self.mock_session.execute.return_value.fetchone.return_value = (0,)
        result = json.loads(self._call_tool("Montreal"))
        assert result["query"] == "Montreal"

    def test_empty_results(self):
        """Returns empty results list when no feeds match."""
        self.mock_session.execute.return_value.fetchall.return_value = []
        self.mock_session.execute.return_value.fetchone.return_value = (0,)
        result = json.loads(self._call_tool("xyznonexistent"))
        assert result["total_matches"] == 0
        assert result["results"] == []

    def test_result_schema(self):
        """Each result has the expected fields."""
        row = make_feed_row()
        self.mock_session.execute.return_value.fetchall.return_value = [row]
        self.mock_session.execute.return_value.fetchone.return_value = (1,)
        result = json.loads(self._call_tool("Montreal"))
        assert len(result["results"]) == 1
        feed = result["results"][0]
        assert "feed_id" in feed
        assert "provider" in feed
        assert "feed_name" in feed
        assert "data_type" in feed
        assert "status" in feed
        assert "is_official" in feed
        assert "locations" in feed
        assert "latest_dataset" in feed
        assert "validation_summary" in feed
        assert "features" in feed
        assert "search_rank" in feed

    def test_result_values_correct(self):
        """Result values are correctly mapped from DB row."""
        row = make_feed_row(
            feed_stable_id="mdb-956",
            provider="STM",
            data_type="gtfs",
            official=True,
            rank=0.95,
        )
        self.mock_session.execute.return_value.fetchall.return_value = [row]
        self.mock_session.execute.return_value.fetchone.return_value = (1,)
        result = json.loads(self._call_tool("STM"))
        feed = result["results"][0]
        assert feed["feed_id"] == "mdb-956"
        assert feed["provider"] == "STM"
        assert feed["data_type"] == "gtfs"
        assert feed["is_official"] is True
        assert abs(feed["search_rank"] - 0.95) < 0.01

    def test_validation_summary_in_result(self):
        """Validation summary fields are present."""
        row = make_feed_row(latest_total_error=3, latest_total_warning=7, latest_total_info=2)
        self.mock_session.execute.return_value.fetchall.return_value = [row]
        self.mock_session.execute.return_value.fetchone.return_value = (1,)
        result = json.loads(self._call_tool("test"))
        feed = result["results"][0]
        assert feed["validation_summary"]["total_error"] == 3
        assert feed["validation_summary"]["total_warning"] == 7
        assert feed["validation_summary"]["total_info"] == 2

    def test_locations_in_result(self):
        """Locations array is included in result for disambiguation."""
        locations = [{"country_code": "CA", "country": "Canada", "subdivision_name": "Quebec", "municipality": "Montreal"}]
        row = make_feed_row(locations=locations)
        self.mock_session.execute.return_value.fetchall.return_value = [row]
        self.mock_session.execute.return_value.fetchone.return_value = (1,)
        result = json.loads(self._call_tool("Montreal"))
        feed = result["results"][0]
        assert feed["locations"] == locations

    def test_empty_query_returns_all_feeds(self):
        """Empty search_query returns all feeds without text filter."""
        self.mock_session.execute.return_value.fetchall.return_value = []
        self.mock_session.execute.return_value.fetchone.return_value = (5,)
        result = json.loads(self._call_tool(""))
        assert result["query"] == ""
        assert result["total_matches"] == 5

    def test_none_fields_handled_gracefully(self):
        """None values in DB row are handled without exceptions."""
        row = make_feed_row(
            feed_name=None,
            latest_dataset_id=None,
            latest_dataset_hosted_url=None,
            latest_dataset_downloaded_at=None,
            latest_total_error=None,
            latest_dataset_features=None,
        )
        row._mapping["locations"] = None
        self.mock_session.execute.return_value.fetchall.return_value = [row]
        self.mock_session.execute.return_value.fetchone.return_value = (1,)
        # Should not raise
        result = json.loads(self._call_tool("test"))
        feed = result["results"][0]
        assert feed["feed_name"] is None
        assert feed["locations"] == []
        assert feed["features"] == []
