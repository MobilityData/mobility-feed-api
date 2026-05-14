"""
Unit tests for the query_gtfs MCP tool.
Tests use mocking to avoid requiring a live database or network.
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch

import duckdb

mock_database_module = MagicMock()
mock_database_class = MagicMock()
mock_db_instance = MagicMock()
mock_database_class.return_value = mock_db_instance
mock_database_module.Database = mock_database_class

mock_models_module = MagicMock()
mock_gtfsfeed = MagicMock()
mock_gtfsfeed.stable_id = MagicMock()
mock_models_module.Gtfsfeed = mock_gtfsfeed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_con(tables: dict[str, list[dict[str, str]]]) -> duckdb.DuckDBPyConnection:
    """Build an in-memory DuckDB with tables from row dicts.

    Args:
        tables: mapping of table_name -> list of row dicts
                e.g. {"stops": [{"stop_id": "1", "stop_name": "Main St"}]}
    """
    con = duckdb.connect()
    for table_name, rows in tables.items():
        if not rows:
            continue
        columns = list(rows[0].keys())
        col_defs = ", ".join(f'"{c}" VARCHAR' for c in columns)
        con.execute(f'CREATE TABLE "{table_name}" ({col_defs})')
        placeholders = ", ".join(["?"] * len(columns))
        for row in rows:
            con.execute(
                f'INSERT INTO "{table_name}" VALUES ({placeholders})',
                [row[c] for c in columns],
            )
    return con


class TestQueryGtfsTool:
    def setup_method(self):
        self.mock_session = MagicMock()
        self.mock_query = MagicMock()
        self.mock_filtered_query = MagicMock()
        self.mock_session.query.return_value = self.mock_query
        self.mock_query.filter.return_value = self.mock_filtered_query
        self.mock_filtered_query.first.return_value = None
        mock_db_instance.start_db_session.return_value.__enter__ = MagicMock(return_value=self.mock_session)
        mock_db_instance.start_db_session.return_value.__exit__ = MagicMock(return_value=False)

    def _import_tool(self):
        for module_name in ["tools.query_gtfs", "tools", "gtfs_cache"]:
            sys.modules.pop(module_name, None)

        with patch.dict(
            sys.modules,
            {
                "shared": MagicMock(),
                "shared.database": MagicMock(),
                "shared.database.database": mock_database_module,
                "shared.database_gen": MagicMock(),
                "shared.database_gen.sqlacodegen_models": mock_models_module,
            },
        ):
            from tools import query_gtfs as module
        return module

    def _make_feed(self, dataset=None):
        feed = MagicMock()
        feed.latest_dataset = dataset
        return feed

    def _make_dataset(self, stable_id="mdb-1210-202402121801"):
        dataset = MagicMock()
        dataset.stable_id = stable_id
        return dataset

    def _call_tool(self, module, query="SCHEMA", feed_id="mdb-1210", bucket_url="https://example.com", con=None, files=None):
        original = os.environ.get("DATASETS_BUCKET_URL")
        if bucket_url:
            os.environ["DATASETS_BUCKET_URL"] = bucket_url
        elif "DATASETS_BUCKET_URL" in os.environ:
            del os.environ["DATASETS_BUCKET_URL"]
        try:
            if con is not None:
                with patch.object(module, "_load_duckdb", return_value=con):
                    return module.query_gtfs_tool(feed_id=feed_id, query=query, files=files)
            return module.query_gtfs_tool(feed_id=feed_id, query=query, files=files)
        finally:
            if original is not None:
                os.environ["DATASETS_BUCKET_URL"] = original
            elif "DATASETS_BUCKET_URL" in os.environ:
                del os.environ["DATASETS_BUCKET_URL"]

    def test_feed_not_found(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = None
        result = json.loads(self._call_tool(module))
        assert result == {"error": "Feed 'mdb-1210' not found."}

    def test_no_dataset(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=None)
        result = json.loads(self._call_tool(module))
        assert result == {"error": "Feed 'mdb-1210' has no dataset yet."}

    def test_schema_mode(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=self._make_dataset())
        con = _make_con({
            "stops": [{"stop_id": "1", "stop_name": "Main St"}, {"stop_id": "2", "stop_name": "Second St"}],
            "routes": [{"route_id": "10", "route_short_name": "10"}],
        })
        result = json.loads(self._call_tool(module, query="SCHEMA", con=con))
        assert result["feed_id"] == "mdb-1210"
        assert result["dataset_id"] == "mdb-1210-202402121801"
        assert result["tables"]["stops"]["columns"] == ["stop_id", "stop_name"]
        assert result["tables"]["stops"]["row_count"] == 2
        assert result["tables"]["routes"]["row_count"] == 1
        assert result["available_files"] == ["routes.txt", "stops.txt"]

    def test_schema_mode_case_insensitive(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=self._make_dataset())
        con = _make_con({"stops": [{"stop_id": "1", "stop_name": "Main St"}]})
        result = json.loads(self._call_tool(module, query="schema", con=con))
        assert result["tables"]["stops"]["columns"] == ["stop_id", "stop_name"]

    def test_select_query_returns_results(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=self._make_dataset())
        con = _make_con({"stops": [{"stop_id": "1", "stop_name": "Main St"}, {"stop_id": "2", "stop_name": "Second St"}]})
        result = json.loads(
            self._call_tool(
                module,
                query="SELECT stop_id, stop_name FROM stops ORDER BY stop_id",
                con=con,
            )
        )
        assert result["columns"] == ["stop_id", "stop_name"]
        assert result["rows"] == [["1", "Main St"], ["2", "Second St"]]
        assert result["row_count"] == 2
        assert isinstance(result["execution_time_ms"], int)
        assert result["execution_time_ms"] >= 0
        assert "LIMIT 1000" in result["sql"]

    def test_non_select_rejected(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=self._make_dataset())
        con = _make_con({})
        result = json.loads(self._call_tool(module, query="DELETE FROM stops", con=con))
        assert "SELECT" in result["error"]

    def test_schema_only_shows_loaded_tables(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=self._make_dataset())
        con = _make_con({"stops": [{"stop_id": "1", "stop_name": "Main St"}]})
        result = json.loads(self._call_tool(module, query="SCHEMA", con=con))
        assert list(result["tables"].keys()) == ["stops"]
        assert result["available_files"] == ["stops.txt"]

    def test_cache_hit(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=self._make_dataset())
        con = duckdb.connect()
        con.execute("CREATE TABLE stops (stop_id VARCHAR)")
        con.execute("INSERT INTO stops VALUES ('1')")

        with patch.dict("os.environ", {"DATASETS_BUCKET_URL": "https://example.com"}), patch.object(
            module, "_load_duckdb", return_value=con
        ) as mock_loader:
            first = json.loads(module.query_gtfs_tool(feed_id="mdb-1210", query="SELECT * FROM stops"))
            second = json.loads(module.query_gtfs_tool(feed_id="mdb-1210", query="SELECT * FROM stops"))

        assert first["rows"] == [["1"]]
        assert second["rows"] == [["1"]]
        assert mock_loader.call_count == 1

    def test_datasets_bucket_url_missing(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=self._make_dataset())
        result = json.loads(self._call_tool(module, bucket_url=""))
        assert result == {"error": "DATASETS_BUCKET_URL is not configured."}

    def test_files_parameter_limits_loaded_tables(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=self._make_dataset())
        con = _make_con({
            "stops": [{"stop_id": "1", "stop_name": "Main St"}],
            "routes": [{"route_id": "10", "route_short_name": "10"}],
        })
        result = json.loads(self._call_tool(module, query="SCHEMA", con=con, files=["stops", "routes"]))
        assert "stops" in result["tables"]
        assert "routes" in result["tables"]
        assert "trips" not in result["tables"]

    def test_files_parameter_accepts_txt_suffix(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=self._make_dataset())
        con = _make_con({"agency": [{"agency_id": "A1", "agency_name": "Transit Co"}]})
        result = json.loads(self._call_tool(module, query="SCHEMA", con=con, files=["agency.txt"]))
        assert "agency" in result["tables"]

    def test_query_infers_tables_when_files_not_provided(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=self._make_dataset())
        con = _make_con({"routes": [{"route_id": "10", "route_short_name": "10"}]})
        with patch.object(module, "_load_duckdb", return_value=con) as spy:
            result = json.loads(
                self._call_tool(
                    module,
                    query="SELECT * FROM routes",
                    con=None,
                    files=None,
                )
            )
            loaded_files = spy.call_args[0][3]
            assert loaded_files == ["routes.txt"]
        assert result["columns"] == ["route_id", "route_short_name"]

    def test_files_parameter_invalid_names_return_error(self):
        module = self._import_tool()
        self.mock_filtered_query.first.return_value = self._make_feed(dataset=self._make_dataset())
        result = json.loads(self._call_tool(module, query="SCHEMA", files=["stops", "bogus"]))
        assert "error" in result
        assert "bogus" in result["error"]
        assert "Valid files are" in result["error"]
