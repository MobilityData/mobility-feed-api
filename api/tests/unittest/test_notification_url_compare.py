from unittest.mock import patch

from shared.notifications.notification_event_service import (
    emit_url_replaced,
    normalize_url_for_strict_compare,
    urls_differ,
    _emit,
)


def test_normalize_url_for_strict_compare_strips_and_casefolds():
    assert normalize_url_for_strict_compare("  HTTPS://Example.com/Feed.zip  ") == "https://example.com/feed.zip"
    assert normalize_url_for_strict_compare(None) == ""


def test_urls_differ_ignores_case_and_surrounding_whitespace():
    assert urls_differ("https://example.com", " HTTPS://Example.com ") is False
    assert urls_differ("https://example.com/a", "https://example.com/b") is True
    assert urls_differ(None, "") is False


def test_strict_compare_treats_protocol_and_www_as_changes():
    # "strict" compare intentionally does NOT normalize protocol or the www. prefix,
    # so these differences must be reported as a URL change.
    assert urls_differ("https://example.com", "http://www.example.com/") is True
    assert normalize_url_for_strict_compare("https://example.com") != normalize_url_for_strict_compare(
        "http://www.example.com/"
    )
    # Protocol-only difference.
    assert urls_differ("http://example.com/feed.zip", "https://example.com/feed.zip") is True
    # www-only difference.
    assert urls_differ("https://example.com/feed.zip", "https://www.example.com/feed.zip") is True


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


def test_emit_url_replaced_merges_extra_data_into_payload():
    with patch("shared.notifications.notification_event_service._emit") as mock_emit:
        emit_url_replaced(
            feed_stable_id="mdb-1",
            old_url="https://example.com/old.zip",
            new_url="https://example.com/new.zip",
            source="unit_test",
            extra_data={"note": "manual"},
        )
        payload = mock_emit.call_args.kwargs["payload"]
        assert payload["note"] == "manual"
        assert payload["old_url"] == "https://example.com/old.zip"


def test_emit_skips_when_users_db_not_configured():
    # When USERS_DATABASE_URL is unset, _emit is a no-op (never touches the DB).
    with patch("shared.notifications.notification_event_service.os.getenv", return_value=None), patch(
        "shared.notifications.notification_event_service._persist_event"
    ) as mock_persist:
        _emit(
            notification_type_id="feed.url_updated",
            event_subtype="url_replaced",
            source="unit_test",
            feeds=[("mdb-1", "subject")],
            payload={"old_url": "o", "new_url": "n"},
        )
        mock_persist.assert_not_called()


def test_emit_persists_when_users_db_configured():
    # When configured, _emit delegates to _persist_event (which writes + commits).
    with patch(
        "shared.notifications.notification_event_service.os.getenv",
        return_value="postgresql://user:pass@localhost/db",
    ), patch("shared.notifications.notification_event_service._persist_event") as mock_persist:
        _emit(
            notification_type_id="feed.url_updated",
            event_subtype="url_replaced",
            source="unit_test",
            feeds=[("mdb-1", "subject")],
            payload={"old_url": "o", "new_url": "n"},
        )
        mock_persist.assert_called_once()


def test_emit_swallows_persist_failure():
    # A failure while persisting must be logged and swallowed (fire-and-forget).
    with patch(
        "shared.notifications.notification_event_service.os.getenv",
        return_value="postgresql://user:pass@localhost/db",
    ), patch(
        "shared.notifications.notification_event_service._persist_event",
        side_effect=RuntimeError("commit failed"),
    ):
        # Must not raise.
        _emit(
            notification_type_id="feed.url_updated",
            event_subtype="url_replaced",
            source="unit_test",
            feeds=[("mdb-1", "subject")],
            payload={"old_url": "o", "new_url": "n"},
        )
