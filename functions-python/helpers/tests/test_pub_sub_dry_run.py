import json
import unittest
from unittest.mock import MagicMock, patch

from pub_sub import trigger_dataset_download


def _feed():
    feed = MagicMock()
    feed.producer_url = "https://example.com/gtfs.zip"
    feed.stable_id = "mdb-1"
    feed.id = "feed-1"
    feed.authentication_type = 0
    feed.authentication_info_url = None
    feed.api_key_parameter_name = None
    return feed


def _published_message(**kwargs):
    publisher = MagicMock()
    with patch("pub_sub.get_pubsub_client", return_value=publisher):
        trigger_dataset_download(_feed(), "exec-1", topic_name="topic", **kwargs)
    return json.loads(publisher.publish.call_args.kwargs["data"].decode())


class TestTriggerDatasetDownload(unittest.TestCase):
    def test_nightly_message_is_unchanged(self):
        message = _published_message()
        self.assertNotIn("dry_run", message)
        self.assertNotIn("headers", message)
        self.assertNotIn("record_source", message)

    def test_dry_run_message_carries_flag_and_headers(self):
        message = _published_message(dry_run=True, headers={"User-Agent": "curl/8.0"})
        self.assertTrue(message["dry_run"])
        self.assertEqual(message["headers"], {"User-Agent": "curl/8.0"})

    def test_record_source_is_sent_when_set(self):
        message = _published_message(record_source="dataset_download_manual")
        self.assertEqual(message["record_source"], "dataset_download_manual")
        self.assertNotIn("dry_run", message)
