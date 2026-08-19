"""Regression tests for OperationsApiImpl.detect_changes and its normalization helpers.

These guard the fix for phantom update changes reported from Retool, where an unchanged
feed was flagged as modified on source_info.license_is_spdx (a derived/read-only field)
and source_info.license_notes (None vs empty-string). Change detection must:
  * ignore derived fields the update request cannot set (license_is_spdx), and
  * treat "absent" representations (None, "", []) as equivalent for every field,
mirroring what to_orm actually persists.
"""

from types import SimpleNamespace

from feeds_gen.models.external_id import ExternalId
from feeds_gen.models.feed_status import FeedStatus
from feeds_gen.models.source_info import SourceInfo
from feeds_gen.models.update_request_gtfs_feed import UpdateRequestGtfsFeed
from feeds_operations.impl.feeds_operations_impl import (
    OperationsApiImpl,
    _normalize_for_diff,
    _strip_derived_fields,
)


def _make_request(source_info: SourceInfo, **overrides) -> UpdateRequestGtfsFeed:
    payload = dict(
        id="mdb-40",
        status=FeedStatus.ACTIVE,
        provider="provider A",
        feed_name="Feed name",
        note="note",
        feed_contact_email="a@example.com",
        source_info=source_info,
        redirects=[],
        external_ids=[],
        operational_status_action="no_change",
        official=True,
    )
    payload.update(overrides)
    return UpdateRequestGtfsFeed(**payload)


def _detect(current: UpdateRequestGtfsFeed, requested: UpdateRequestGtfsFeed):
    # detect_changes only needs impl_class.from_orm(feed) to yield the current projection;
    # a stub avoids building a full ORM row and keeps the test on the diff logic.
    stub_impl = SimpleNamespace(from_orm=lambda feed: current)
    return OperationsApiImpl.detect_changes(
        feed=object(), update_request_feed=requested, impl_class=stub_impl
    )


def test_detect_changes_ignores_derived_and_empty_representations():
    """The exact Retool scenario: only derived/empty differences -> no changes."""
    current = _make_request(
        SourceInfo(
            producer_url="https://example.com/feed",
            authentication_type=0,
            license_url="https://example.com/license",
            license_notes=None,
            license_is_spdx=True,  # derived from the License relationship
        )
    )
    requested = _make_request(
        SourceInfo(
            producer_url="https://example.com/feed",
            authentication_type=0,
            license_url="https://example.com/license",
            license_notes="",  # Retool sends empty string instead of None
            license_is_spdx=None,  # Retool omits the derived flag
        )
    )

    diff = _detect(current, requested)

    assert not diff.affected_paths


def test_detect_changes_ignores_empty_list_vs_none():
    """redirects/external_ids as [] vs None must not count as a change."""
    source_info = SourceInfo(producer_url="https://example.com/feed")
    current = _make_request(source_info, redirects=[], external_ids=[])
    requested = _make_request(source_info, redirects=None, external_ids=None)

    diff = _detect(current, requested)

    assert not diff.affected_paths


def test_detect_changes_still_detects_real_change():
    """A genuine edit is still reported; normalization does not swallow it."""
    source_info = SourceInfo(producer_url="https://example.com/feed")
    current = _make_request(source_info)
    requested = _make_request(source_info, feed_name="Renamed feed")

    diff = _detect(current, requested)

    assert diff.affected_paths


def test_detect_changes_detects_cleared_list():
    """Clearing a non-empty list (real intent) is not masked by empty normalization."""
    source_info = SourceInfo(producer_url="https://example.com/feed")
    current = _make_request(
        source_info,
        external_ids=[ExternalId(external_id="e1", source="s1")],
    )
    requested = _make_request(source_info, external_ids=[])

    diff = _detect(current, requested)

    assert diff.affected_paths


def test_normalize_for_diff_coerces_empty_values():
    normalized = _normalize_for_diff(
        {
            "empty_str": "",
            "empty_list": [],
            "kept_str": "value",
            "nested": {"inner_empty": "", "inner_list": [{"x": ""}]},
        }
    )
    assert normalized == {
        "empty_str": None,
        "empty_list": None,
        "kept_str": "value",
        "nested": {"inner_empty": None, "inner_list": [{"x": None}]},
    }


def test_strip_derived_fields_removes_license_is_spdx():
    dumped = {"source_info": {"license_is_spdx": True, "license_url": "u"}}
    _strip_derived_fields(dumped)
    assert "license_is_spdx" not in dumped["source_info"]
    assert dumped["source_info"]["license_url"] == "u"


def test_strip_derived_fields_tolerates_missing_source_info():
    dumped = {"source_info": None}
    # Must not raise when source_info is absent/None.
    assert _strip_derived_fields(dumped) == {"source_info": None}
