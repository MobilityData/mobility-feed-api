from unittest.mock import patch

from shared.notifications.notification_event_service import (
    emit_url_replaced,
    normalize_url,
    urls_differ,
)


def test_normalize_url_strips_and_casefolds():
    assert normalize_url("  HTTPS://Example.com/Feed.zip  ") == "https://example.com/feed.zip"
    assert normalize_url(None) == ""


def test_urls_differ_ignores_case_and_surrounding_whitespace():
    assert urls_differ("https://example.com", " HTTPS://Example.com ") is False
    assert urls_differ("https://example.com/a", "https://example.com/b") is True
    assert urls_differ(None, "") is False


def test_emit_url_replaced_skips_equivalent_urls():
    with patch("shared.notifications.notification_event_service._emit") as mock_emit:
        emit_url_replaced(
            feed_stable_id="mdb-1",
            old_url="https://example.com/feed.zip",
            new_url="  HTTPS://Example.com/feed.zip ",
            source="unit_test",
        )
        mock_emit.assert_not_called()


def test_emit_url_replaced_emits_on_real_change():
    with patch("shared.notifications.notification_event_service._emit") as mock_emit:
        emit_url_replaced(
            feed_stable_id="mdb-1",
            old_url="https://example.com/old.zip",
            new_url="https://example.com/new.zip",
            source="unit_test",
        )
        mock_emit.assert_called_once()
