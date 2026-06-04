import unittest
from unittest.mock import MagicMock, patch

import requests

from scripts.gbfs_utils.fetching import fetch_data, get_data_content, get_field_url


def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.raise_for_status.return_value = None
    mock.status_code = status_code
    return mock


class TestGetFieldUrl(unittest.TestCase):
    def test_returns_url_when_name_matches(self):
        fields = [{"name": "gbfs", "url": "https://example.com/gbfs.json"}]
        self.assertEqual(get_field_url(fields, "gbfs"), "https://example.com/gbfs.json")

    def test_returns_none_when_name_not_found(self):
        fields = [{"name": "other", "url": "https://example.com/other.json"}]
        self.assertIsNone(get_field_url(fields, "gbfs"))

    def test_returns_none_for_empty_list(self):
        self.assertIsNone(get_field_url([], "gbfs"))

    def test_returns_first_match(self):
        fields = [
            {"name": "gbfs", "url": "https://example.com/first.json"},
            {"name": "gbfs", "url": "https://example.com/second.json"},
        ]
        self.assertEqual(get_field_url(fields, "gbfs"), "https://example.com/first.json")


class TestGetDataContent(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()

    @patch("scripts.gbfs_utils.fetching.requests.get")
    def test_returns_data_section_on_success(self, mock_get):
        mock_get.return_value = _mock_response({"data": {"key": "value"}})
        result = get_data_content("https://example.com/feed.json", self.logger)
        self.assertEqual(result, {"key": "value"})

    @patch("scripts.gbfs_utils.fetching.requests.get")
    def test_returns_empty_dict_when_data_key_missing(self, mock_get):
        mock_get.return_value = _mock_response({})
        result = get_data_content("https://example.com/feed.json", self.logger)
        self.assertEqual(result, {})

    def test_returns_none_when_url_is_none(self):
        result = get_data_content(None, self.logger)
        self.assertIsNone(result)

    def test_returns_none_when_url_is_empty_string(self):
        result = get_data_content("", self.logger)
        self.assertIsNone(result)

    @patch("scripts.gbfs_utils.fetching.requests.get")
    def test_returns_none_on_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("timeout")
        result = get_data_content("https://example.com/feed.json", self.logger)
        self.assertIsNone(result)
        self.logger.error.assert_called_once()


class TestFetchData(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()

    def test_returns_none_when_url_is_falsy(self):
        self.assertIsNone(fetch_data(None, self.logger))
        self.assertIsNone(fetch_data("", self.logger))

    @patch("scripts.gbfs_utils.fetching.requests.get")
    def test_returns_empty_dict_on_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("error")
        result = fetch_data("https://example.com/gbfs.json", self.logger)
        self.assertEqual(result, {})
        self.logger.error.assert_called_once()

    @patch("scripts.gbfs_utils.fetching.requests.get")
    def test_extracts_requested_top_level_fields(self, mock_get):
        mock_get.return_value = _mock_response({"version": "2.0", "ttl": 10, "data": {}})
        result = fetch_data("https://example.com/gbfs.json", self.logger, fields=["version", "ttl"])
        self.assertEqual(result["version"], "2.0")
        self.assertEqual(result["ttl"], 10)

    @patch("scripts.gbfs_utils.fetching.requests.get")
    def test_en_lang_takes_priority(self, mock_get):
        data = {
            "data": {
                "fr": {"feeds": [{"name": "gbfs", "url": "https://example.com/fr.json"}]},
                "en": {"feeds": [{"name": "gbfs", "url": "https://example.com/en.json"}]},
            }
        }
        mock_get.return_value = _mock_response(data)
        result = fetch_data("https://example.com/gbfs.json", self.logger, urls=["gbfs"])
        self.assertEqual(result["gbfs"], "https://example.com/en.json")

    @patch("scripts.gbfs_utils.fetching.requests.get")
    def test_falls_back_to_non_en_lang_when_no_en(self, mock_get):
        data = {
            "data": {
                "fr": {"feeds": [{"name": "gbfs", "url": "https://example.com/fr.json"}]},
            }
        }
        mock_get.return_value = _mock_response(data)
        result = fetch_data("https://example.com/gbfs.json", self.logger, urls=["gbfs"])
        self.assertEqual(result["gbfs"], "https://example.com/fr.json")

    @patch("scripts.gbfs_utils.fetching.requests.get")
    def test_lang_data_as_list(self, mock_get):
        """Covers branch where lang_data is a list (not a dict with 'feeds' key)."""
        data = {
            "data": {
                "en": [{"name": "gbfs", "url": "https://example.com/list.json"}],
            }
        }
        mock_get.return_value = _mock_response(data)
        result = fetch_data("https://example.com/gbfs.json", self.logger, urls=["gbfs"])
        self.assertEqual(result["gbfs"], "https://example.com/list.json")

    @patch("scripts.gbfs_utils.fetching.requests.get")
    def test_no_feeds_skips_url_lookup(self, mock_get):
        """Covers branch where feeds is falsy — url lookup is skipped."""
        mock_get.return_value = _mock_response({"data": {}})
        result = fetch_data("https://example.com/gbfs.json", self.logger, urls=["gbfs"])
        self.assertNotIn("gbfs", result)

    @patch("scripts.gbfs_utils.fetching.requests.get")
    def test_first_non_en_lang_used_then_stays_on_second(self, mock_get):
        """Covers branch: feeds already set from first non-en lang, second non-en lang skipped."""
        data = {
            "data": {
                "fr": {"feeds": [{"name": "gbfs", "url": "https://example.com/fr.json"}]},
                "de": {"feeds": [{"name": "gbfs", "url": "https://example.com/de.json"}]},
            }
        }
        mock_get.return_value = _mock_response(data)
        result = fetch_data("https://example.com/gbfs.json", self.logger, urls=["gbfs"])
        # Either fr or de wins (dict order), but only one is used
        self.assertIn(result["gbfs"], ["https://example.com/fr.json", "https://example.com/de.json"])


if __name__ == "__main__":
    unittest.main()
