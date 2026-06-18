from unittest.mock import MagicMock, patch

from shared.notifications.notification_event_service import (
    emit_url_replaced,
    normalize_url,
    urls_differ,
    _emit,
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


def test_emit_swallows_import_error(caplog):
    import sys

    # Force `from shared.database.users_database import UsersDatabase` to raise
    # ImportError inside _emit; the call must degrade gracefully (no raise).
    with patch.dict(sys.modules, {"shared.database.users_database": None}):
        _emit(
            notification_type_id="feed.url_updated",
            event_subtype="url_replaced",
            source="unit_test",
            feeds=[("mdb-1", "subject")],
            payload={"old_url": "o", "new_url": "n"},
        )


def test_emit_swallows_users_db_unavailable():
    # UsersDatabase() construction failing must not raise out of _emit.
    with patch(
        "shared.database.users_database.UsersDatabase",
        side_effect=RuntimeError("no users db"),
    ):
        _emit(
            notification_type_id="feed.url_updated",
            event_subtype="url_replaced",
            source="unit_test",
            feeds=[("mdb-1", "subject")],
            payload={"old_url": "o", "new_url": "n"},
        )


def test_emit_swallows_persist_failure():
    # A failure while persisting must be logged and swallowed (fire-and-forget).
    fake_db = MagicMock()
    fake_db.start_db_session.side_effect = RuntimeError("commit failed")
    with patch("shared.database.users_database.UsersDatabase", return_value=fake_db):
        _emit(
            notification_type_id="feed.url_updated",
            event_subtype="url_replaced",
            source="unit_test",
            feeds=[("mdb-1", "subject")],
            payload={"old_url": "o", "new_url": "n"},
        )
