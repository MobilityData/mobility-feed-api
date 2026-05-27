"""
Unit tests for the get_validation_results MCP tool.
Tests use mocking to avoid requiring a live database or network.
"""
import json
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

mock_database_module = MagicMock()
mock_database_class = MagicMock()
mock_db_instance = MagicMock()
mock_database_class.return_value = mock_db_instance
mock_database_module.Database = mock_database_class

mock_models_module = MagicMock()
mock_gtfsfeed = MagicMock()
mock_gtfsfeed.stable_id = MagicMock()
mock_gtfsfeed.latest_dataset = MagicMock()
mock_gtfsdataset = MagicMock()
mock_gtfsdataset.validation_reports = MagicMock()
mock_validationreport = MagicMock()
mock_validationreport.notices = MagicMock()
mock_validationreport.features = MagicMock()
mock_models_module.Gtfsfeed = mock_gtfsfeed
mock_models_module.Gtfsdataset = mock_gtfsdataset
mock_models_module.Validationreport = mock_validationreport

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class MockJoinedLoad:
    def joinedload(self, *_args, **_kwargs):
        return self


class TestGetValidationResultsTool:
    def setup_method(self):
        self.mock_session = MagicMock()
        self.mock_query = MagicMock()
        self.mock_filtered_query = MagicMock()
        self.mock_options_query = MagicMock()
        self.mock_session.query.return_value = self.mock_query
        self.mock_query.filter.return_value = self.mock_filtered_query
        self.mock_filtered_query.options.return_value = self.mock_options_query
        self.mock_options_query.first.return_value = None
        mock_db_instance.start_db_session.return_value.__enter__ = MagicMock(return_value=self.mock_session)
        mock_db_instance.start_db_session.return_value.__exit__ = MagicMock(return_value=False)

        self.mock_rules_cache = MagicMock()
        self.mock_rules_cache.get_dict.return_value = None
        self.mock_joinedload = MagicMock(return_value=MockJoinedLoad())

    def _import_tool(self):
        for module_name in ["tools.get_validation_results", "tools"]:
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
            from tools import get_validation_results as module
        return module

    def _call_tool(self, feed_id="mdb-1210", severity_filter="all"):
        module = self._import_tool()
        with patch.object(module, "get_rules_cache", return_value=self.mock_rules_cache), patch.object(
            module, "joinedload", self.mock_joinedload
        ):
            return module.get_validation_results_tool(feed_id=feed_id, severity_filter=severity_filter)

    def _make_notice(self, code="missing_stop_name", severity="ERROR", total_notices=3):
        notice = MagicMock()
        notice.notice_code = code
        notice.severity = severity
        notice.total_notices = total_notices
        return notice

    def _make_report(self, notices=None, features=None, validated_at=None):
        report = MagicMock()
        report.validated_at = validated_at or datetime(2024, 2, 12, 18, 1, 0)
        report.validator_version = "7.1.0"
        report.json_report = "https://example.com/report.json"
        report.html_report = "https://example.com/report.html"
        report.total_error = 2
        report.total_warning = 1
        report.total_info = 0
        report.unique_error_count = 1
        report.unique_warning_count = 1
        report.unique_info_count = 0
        report.notices = notices or []
        report.features = features or []
        return report

    def _make_feed(self, dataset=None, provider="Test Provider"):
        feed = MagicMock()
        feed.provider = provider
        feed.latest_dataset = dataset
        return feed

    def _make_dataset(self, stable_id="mdb-1210-202402121801", validation_reports=None):
        dataset = MagicMock()
        dataset.stable_id = stable_id
        dataset.validation_reports = validation_reports or []
        return dataset

    def test_feed_not_found(self):
        self.mock_options_query.first.return_value = None
        result = json.loads(self._call_tool())
        assert result == {"error": "Feed 'mdb-1210' not found."}

    def test_no_dataset(self):
        self.mock_options_query.first.return_value = self._make_feed(dataset=None)
        result = json.loads(self._call_tool())
        assert result == {"error": "Feed 'mdb-1210' has no dataset yet."}

    def test_no_validation_report(self):
        dataset = self._make_dataset(validation_reports=[])
        self.mock_options_query.first.return_value = self._make_feed(dataset=dataset)
        result = json.loads(self._call_tool())
        assert result["feed_id"] == "mdb-1210"
        assert result["provider"] == "Test Provider"
        assert result["dataset_id"] == dataset.stable_id
        assert result["error"] == "No validation report found for this feed."

    def test_returns_valid_json(self):
        feature = MagicMock()
        feature.name = "fares-v2"
        notice = self._make_notice()
        report = self._make_report(notices=[notice], features=[feature])
        dataset = self._make_dataset(validation_reports=[report])
        self.mock_options_query.first.return_value = self._make_feed(dataset=dataset, provider="Agency")

        result = json.loads(self._call_tool())
        assert result["feed_id"] == "mdb-1210"
        assert result["provider"] == "Agency"
        assert result["dataset_id"] == dataset.stable_id
        assert result["validator_version"] == "7.1.0"
        assert result["report_urls"]["json"] == "https://example.com/report.json"
        assert result["gtfs_features"] == ["fares-v2"]
        assert result["summary"]["total_errors"] == 2
        assert len(result["notices"]) == 1

    def test_severity_filter_errors(self):
        error_notice = self._make_notice(code="error_code", severity="ERROR")
        warning_notice = self._make_notice(code="warning_code", severity="WARNING")
        report = self._make_report(notices=[warning_notice, error_notice])
        dataset = self._make_dataset(validation_reports=[report])
        self.mock_options_query.first.return_value = self._make_feed(dataset=dataset)

        result = json.loads(self._call_tool(severity_filter="errors"))
        assert [notice["code"] for notice in result["notices"]] == ["error_code"]

    def test_severity_filter_warnings(self):
        error_notice = self._make_notice(code="error_code", severity="ERROR")
        warning_notice = self._make_notice(code="warning_code", severity="WARNING")
        report = self._make_report(notices=[error_notice, warning_notice])
        dataset = self._make_dataset(validation_reports=[report])
        self.mock_options_query.first.return_value = self._make_feed(dataset=dataset)

        result = json.loads(self._call_tool(severity_filter="warnings"))
        assert [notice["code"] for notice in result["notices"]] == ["warning_code"]

    def test_rule_doc_enrichment(self):
        self.mock_rules_cache.get_dict.return_value = {
            "description": "Missing stop name",
            "short_summary": "Stop name missing",
            "affected_files": ["stops.txt"],
            "rule_url": "https://example.com/rule",
        }
        notice = self._make_notice(code="missing_stop_name")
        report = self._make_report(notices=[notice])
        dataset = self._make_dataset(validation_reports=[report])
        self.mock_options_query.first.return_value = self._make_feed(dataset=dataset)

        result = json.loads(self._call_tool())
        assert result["notices"][0]["rule_doc"]["description"] == "Missing stop name"

    def test_affected_file_fetched(self):
        self.mock_rules_cache.get_dict.return_value = {
            "description": "Missing stop name",
            "short_summary": "Stop name missing",
            "affected_files": ["stops.txt"],
            "rule_url": "https://example.com/rule",
        }
        notice = self._make_notice(code="missing_stop_name")
        report = self._make_report(notices=[notice])
        dataset = self._make_dataset(validation_reports=[report])
        self.mock_options_query.first.return_value = self._make_feed(dataset=dataset)

        module = self._import_tool()
        response = MagicMock()
        response.status_code = 200
        response.text = "stop_id,stop_name\n1,Main St\n2,Second St\n"
        response.raise_for_status = MagicMock()
        client = MagicMock()
        client.get.return_value = response
        client.__enter__.return_value = client
        client.__exit__.return_value = False

        with patch.dict("os.environ", {"DATASETS_BUCKET_URL": "https://example.com"}), patch.object(
            module, "get_rules_cache", return_value=self.mock_rules_cache
        ), patch.object(module, "joinedload", self.mock_joinedload), patch.object(module.httpx, "Client", return_value=client):
            result = json.loads(module.get_validation_results_tool(feed_id="mdb-1210"))

        affected_file = result["notices"][0]["affected_file"]
        assert affected_file["filename"] == "stops.txt"
        assert affected_file["columns"] == ["stop_id", "stop_name"]
        assert affected_file["total_rows"] == 2
        client.get.assert_called_once_with(
            "https://example.com/mdb-1210/mdb-1210-202402121801/extracted/stops.txt"
        )

    def test_affected_file_404(self):
        self.mock_rules_cache.get_dict.return_value = {
            "description": "Missing stop name",
            "short_summary": "Stop name missing",
            "affected_files": ["stops.txt"],
            "rule_url": "https://example.com/rule",
        }
        notice = self._make_notice(code="missing_stop_name")
        report = self._make_report(notices=[notice])
        dataset = self._make_dataset(validation_reports=[report])
        self.mock_options_query.first.return_value = self._make_feed(dataset=dataset)

        module = self._import_tool()
        response = MagicMock()
        response.status_code = 404
        response.raise_for_status = MagicMock()
        client = MagicMock()
        client.get.return_value = response
        client.__enter__.return_value = client
        client.__exit__.return_value = False

        with patch.dict("os.environ", {"DATASETS_BUCKET_URL": "https://example.com"}), patch.object(
            module, "get_rules_cache", return_value=self.mock_rules_cache
        ), patch.object(module, "joinedload", self.mock_joinedload), patch.object(module.httpx, "Client", return_value=client):
            result = json.loads(module.get_validation_results_tool(feed_id="mdb-1210"))

        assert result["notices"][0]["affected_file"] is None

    def test_file_sample_deduplication(self):
        def get_rule(_code):
            return {
                "description": "Shared file",
                "short_summary": "Shared file",
                "affected_files": ["stops.txt"],
                "rule_url": "https://example.com/rule",
            }

        self.mock_rules_cache.get_dict.side_effect = get_rule
        first_notice = self._make_notice(code="notice_one", total_notices=5)
        second_notice = self._make_notice(code="notice_two", total_notices=1)
        report = self._make_report(notices=[first_notice, second_notice])
        dataset = self._make_dataset(validation_reports=[report])
        self.mock_options_query.first.return_value = self._make_feed(dataset=dataset)

        module = self._import_tool()
        response = MagicMock()
        response.status_code = 200
        response.text = "stop_id,stop_name\n1,Main St\n"
        response.raise_for_status = MagicMock()
        client = MagicMock()
        client.get.return_value = response
        client.__enter__.return_value = client
        client.__exit__.return_value = False

        with patch.dict("os.environ", {"DATASETS_BUCKET_URL": "https://example.com"}), patch.object(
            module, "get_rules_cache", return_value=self.mock_rules_cache
        ), patch.object(module, "joinedload", self.mock_joinedload), patch.object(module.httpx, "Client", return_value=client):
            result = json.loads(module.get_validation_results_tool(feed_id="mdb-1210"))

        assert len(result["notices"]) == 2
        client.get.assert_called_once()
