#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import os
import unittest
import uuid
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from test_shared.test_utils.database_utils import default_db_url
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Feed, Gtfsfeed, Gtfsrealtimefeed

from tasks.data_import.data_import_utils import deprecate_stale_feeds
from tasks.data_import.odpt.import_odpt_feeds import (
    import_odpt_handler,
    _get_license_url,
)

GTFS_ENDPOINT_TMPL = (
    "https://api-public.odpt.org/api/v4/files/odpt/{}/{}.zip?date=current"
)
CC0_URL = "https://creativecommons.org/publicdomain/zero/1.0/"


class _FakeResponse:
    def __init__(self, body=None, status: int = 200):
        self._body = body if body is not None else []
        self.status_code = status

    def json(self):
        return self._body

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise RuntimeError(f"HTTP {self.status_code}")


METADATA_URL_TMPL = (
    "https://members-portal.odpt.org/api/v1/resources?license={}&format={}"
)


class _FakeSessionOK:
    """
    Returns, for license=ccby4: one org/dataset with all 3 RT endpoints (the real,
    persistable feed used by the dry_run=False test).
    Returns, for license=cc0: one org missing its `label` -> skipped by _process_feed
    (org_label is None), exercising that guard clause without creating any row.
    """

    def get(self, url, timeout=60):
        if url == METADATA_URL_TMPL.format("ccby4", "gtfs"):
            return _FakeResponse(
                [
                    {
                        "label": "RealOrg",
                        "name_ja": "リアル組織",
                        "name_en": "Real Org",
                        "datasets": [
                            {
                                "label": "real_dataset",
                                "name_ja": "リアルデータセット",
                                "name_en": "Real Dataset",
                                "license_type": "CC BY 4.0",
                                "vehicle_position": {
                                    "url": "https://rt.example/real/vp.pb"
                                },
                                "trip_update": {"url": "https://rt.example/real/tu.pb"},
                                "alert": {"url": "https://rt.example/real/sa.pb"},
                            }
                        ],
                    }
                ]
            )
        if url == METADATA_URL_TMPL.format("cc0", "gtfs"):
            return _FakeResponse(
                [
                    {
                        # No "label" -> org_label is None -> feed skipped entirely.
                        "name_en": "No Label Org",
                        "datasets": [
                            {
                                "label": "orphan_dataset",
                                "name_en": "Orphan Dataset",
                                "license_type": "CC0",
                            }
                        ],
                    }
                ]
            )
        return _FakeResponse([], 404)


class _FakeSessionDryRun:
    """A distinct org/dataset namespace from _FakeSessionOK, so the dry-run test
    can never collide with rows the other test created (or would have created)."""

    def get(self, url, timeout=60):
        if url == METADATA_URL_TMPL.format("ccby4", "gtfs"):
            return _FakeResponse(
                [
                    {
                        "label": "DryRunOrg",
                        "name_ja": "ドライレン組織",
                        "name_en": "Dry Run Org",
                        "datasets": [
                            {
                                "label": "dry_run_dataset",
                                "name_ja": "ドライレンデータセット",
                                "name_en": "Dry Run Dataset",
                                "license_type": "CC0",
                                "vehicle_position": {
                                    "url": "https://rt.example/dryrun/vp.pb"
                                },
                                "trip_update": {
                                    "url": "https://rt.example/dryrun/tu.pb"
                                },
                            }
                        ],
                    }
                ]
            )
        if url == METADATA_URL_TMPL.format("cc0", "gtfs"):
            return _FakeResponse([])
        return _FakeResponse([], 404)


class _FakeSessionReactivate:
    """
    Returns one dataset whose persisted fields are byte-identical to the row the
    reactivation test pre-seeds -- so the schedule fingerprint matches exactly and
    the ONLY reason not to take the "no change detected" early return is that the
    row is sitting deprecated/unpublished. No RT urls, so the RT maps match too.
    """

    def get(self, url, timeout=60):
        if url == METADATA_URL_TMPL.format("ccby4", "gtfs"):
            return _FakeResponse(
                [
                    {
                        "label": "ReactOrg",
                        "name_ja": "リアクト組織",
                        "datasets": [
                            {
                                "label": "react_dataset",
                                "name_ja": "リアクトデータセット",
                                "license_type": "CC0",
                            }
                        ],
                    }
                ]
            )
        if url == METADATA_URL_TMPL.format("cc0", "gtfs"):
            return _FakeResponse([])
        return _FakeResponse([], 404)


class _FakeSessionRtGranularity:
    """
    Same org/dataset as the RT-granularity test pre-seeds, but advertising only
    trip_update + vehicle_position -- the alert URL has been withdrawn. Only the
    `-sa` RT sub-feed should end up deprecated.
    """

    TU_URL = "https://rt.example/rtgran/tu.pb"
    VP_URL = "https://rt.example/rtgran/vp.pb"

    def get(self, url, timeout=60):
        if url == METADATA_URL_TMPL.format("ccby4", "gtfs"):
            return _FakeResponse(
                [
                    {
                        "label": "RtGranOrg",
                        "name_ja": "RTグラン組織",
                        "datasets": [
                            {
                                "label": "rt_gran_dataset",
                                "name_ja": "RTグランデータセット",
                                "license_type": "CC0",
                                "trip_update": {"url": self.TU_URL},
                                "vehicle_position": {"url": self.VP_URL},
                                # "alert" withdrawn on purpose
                            }
                        ],
                    }
                ]
            )
        if url == METADATA_URL_TMPL.format("cc0", "gtfs"):
            return _FakeResponse([])
        return _FakeResponse([], 404)


class _FakeSessionEmpty:
    """Successful HTTP 200 responses that happen to contain no datasets at all."""

    def get(self, url, timeout=60):
        return _FakeResponse([])


class _FakeSessionError:
    def get(self, url, timeout=60):
        raise RuntimeError("network down")


def _seed_feed(db_session, model, stable_id, data_type, **fields):
    """Insert a feed row directly, bypassing the importer, for sweep/reactivation tests."""
    feed = model(
        id=str(uuid.uuid4()),
        stable_id=stable_id,
        data_type=data_type,
        **fields,
    )
    db_session.add(feed)
    return feed


def _delete_feeds_like(db_session, pattern):
    """Remove seeded rows so they don't leak into the session-scoped shared test DB."""
    db_session.query(Feed).filter(Feed.stable_id.like(pattern)).delete(
        synchronize_session=False
    )
    db_session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Helper function tests
# ─────────────────────────────────────────────────────────────────────────────


class TestHelpers(unittest.TestCase):
    def test_get_license_url_known_and_unknown(self):
        self.assertEqual(
            _get_license_url("CC BY 4.0"),
            "https://creativecommons.org/licenses/by/4.0/",
        )
        self.assertEqual(
            _get_license_url("CC0"),
            "https://creativecommons.org/publicdomain/zero/1.0/",
        )
        self.assertIsNone(_get_license_url("some-unknown-license"))
        self.assertIsNone(_get_license_url(None))

    @with_db_session(db_url=default_db_url)
    def test_deprecate_stale_feeds_only_flips_absent_feeds(self, db_session: Session):
        """
        Unit-test the shared sweep directly, under a private prefix that can never
        collide with the real odpt-/jbda-/tdg- namespaces (the test DB is shared for
        the whole pytest session, so a real prefix here would hit other tests' rows).
        """
        prefix = "odpt-utest-"
        kept_id = f"{prefix}kept"
        dropped_id = f"{prefix}dropped"
        try:
            for stable_id in (kept_id, dropped_id):
                _seed_feed(
                    db_session,
                    Gtfsfeed,
                    stable_id,
                    "gtfs",
                    status="active",
                    operational_status="published",
                )
            db_session.commit()

            newly_deprecated = deprecate_stale_feeds(db_session, prefix, {kept_id})
            db_session.commit()

            self.assertEqual(newly_deprecated, [dropped_id])

            kept = db_session.query(Feed).filter(Feed.stable_id == kept_id).one()
            dropped = db_session.query(Feed).filter(Feed.stable_id == dropped_id).one()
            self.assertEqual(
                (kept.status, kept.operational_status), ("active", "published")
            )
            self.assertEqual(
                (dropped.status, dropped.operational_status),
                ("deprecated", "unpublished"),
            )

            # Idempotent: an already-deprecated feed is not reported a second time,
            # so repeat runs don't re-enqueue revalidation for it.
            self.assertEqual(deprecate_stale_feeds(db_session, prefix, {kept_id}), [])
        finally:
            _delete_feeds_like(db_session, f"{prefix}%")


# ─────────────────────────────────────────────────────────────────────────────
# Import tests
# ─────────────────────────────────────────────────────────────────────────────


class TestImportODPT(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def test_import_creates_gtfs_rt_and_location(self, db_session: Session):
        mock_trigger = MagicMock()
        mock_revalidate = MagicMock()
        with patch(
            "tasks.data_import.odpt.import_odpt_feeds.requests.Session",
            return_value=_FakeSessionOK(),
        ), patch(
            "tasks.data_import.odpt.import_odpt_feeds.REQUEST_TIMEOUT_S", 0.01
        ), patch(
            # commit_changes (and the side effects it triggers) now lives in
            # data_import_utils, shared with jbda/tdg -- patch it there, not on
            # this module, since that's where the name is looked up at call time.
            "tasks.data_import.data_import_utils.trigger_dataset_download",
            mock_trigger,
        ), patch(
            "tasks.data_import.data_import_utils.create_web_revalidation_task",
            mock_revalidate,
        ), patch(
            # This test isn't about the stale sweep. Stub it out so it neither
            # deprecates rows other tests committed into the shared session-scoped
            # test DB, nor makes the "deprecated" count below order-dependent.
            "tasks.data_import.odpt.import_odpt_feeds.deprecate_stale_feeds",
            MagicMock(return_value=[]),
        ), patch.dict(
            # commit_changes skips both side effects when ENVIRONMENT=local
            # (e.g. functions-python/tasks_executor/.env.local); force a
            # non-local value so this test actually exercises them.
            os.environ,
            {"ENVIRONMENT": "test"},
            clear=False,
        ):
            result = import_odpt_handler({"dry_run": False})

        self.assertEqual(
            {
                "message": "ODPT import executed successfully.",
                "created_gtfs": 1,
                "updated_gtfs": 0,
                "created_gtfs_rt": 3,
                "updated_gtfs_rt": 0,
                "deprecated": 0,
                "linked_refs": 3,
                "total_processed_items": 1,
                "params": {"dry_run": False},
            },
            result,
        )

        # The org missing its "label" must not have created anything.
        orphan = (
            db_session.query(Gtfsfeed)
            .filter(Gtfsfeed.stable_id.like("%orphan_dataset%"))
            .first()
        )
        self.assertIsNone(orphan)

        # Schedule feed
        sched = (
            db_session.query(Gtfsfeed)
            .filter(Gtfsfeed.stable_id == "odpt-RealOrg-real_dataset")
            .first()
        )
        self.assertIsNotNone(sched)
        sched = db_session.merge(sched)

        self.assertEqual(sched.feed_name, "リアルデータセット")
        self.assertEqual(sched.provider, "リアル組織")
        self.assertEqual(
            sched.producer_url,
            "https://api-public.odpt.org/api/v4/files/odpt/RealOrg/real_dataset.zip?date=current",
        )
        self.assertEqual(
            sched.license_url, "https://creativecommons.org/licenses/by/4.0/"
        )
        self.assertEqual(sched.status, "active")
        self.assertEqual(sched.operational_status, "published")

        externalids = list(sched.externalids)
        self.assertEqual(len(externalids), 1)
        self.assertEqual(externalids[0].source, "odpt")
        self.assertEqual(externalids[0].associated_id, "RealOrg-real_dataset")

        locations = list(sched.locations)
        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].country, "Japan")

        # RT feeds + entity types & back-links
        tu = db_session.merge(
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == "odpt-RealOrg-real_dataset-tu")
            .first()
        )
        vp = db_session.merge(
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == "odpt-RealOrg-real_dataset-vp")
            .first()
        )
        sa = db_session.merge(
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == "odpt-RealOrg-real_dataset-sa")
            .first()
        )

        for rt_feed, entity_type, url in (
            (tu, "tu", "https://rt.example/real/tu.pb"),
            (vp, "vp", "https://rt.example/real/vp.pb"),
            (sa, "sa", "https://rt.example/real/sa.pb"),
        ):
            self.assertIsNotNone(rt_feed)
            self.assertEqual(len(rt_feed.entitytypes), 1)
            self.assertEqual(rt_feed.entitytypes[0].name, entity_type)
            self.assertEqual([f.id for f in rt_feed.gtfs_feeds], [sched.id])
            self.assertEqual(rt_feed.producer_url, url)

        # Side effects: exactly one new schedule feed -> one download trigger,
        # one revalidation call for that single changed stable_id.
        mock_trigger.assert_called_once()
        published_feed = db_session.merge(mock_trigger.call_args[0][0])
        self.assertEqual(published_feed.stable_id, "odpt-RealOrg-real_dataset")
        self.assertIsInstance(mock_trigger.call_args[0][1], str)

        mock_revalidate.assert_called_once_with(["odpt-RealOrg-real_dataset"])

    @with_db_session(db_url=default_db_url)
    def test_import_dry_run_true_does_not_write_to_db(self, db_session: Session):
        """
        Regression test: a dry run must never persist anything. get_or_create_feed/
        get_or_create_entity_type flush new rows into the session regardless of
        dry_run, and @with_db_session's start_db_session() commits unconditionally
        on a normal return -- _import_odpt must explicitly roll back when dry_run
        is True, or this "dry run" silently writes to the database.
        """
        mock_trigger = MagicMock()
        mock_revalidate = MagicMock()
        # Seed a feed absent from _FakeSessionDryRun's response, so the (unmocked)
        # stale sweep has something to report -- and must still not persist it.
        stale_id = "odpt-DryRunStaleOrg-stale_dataset"
        try:
            _seed_feed(
                db_session,
                Gtfsfeed,
                stale_id,
                "gtfs",
                status="active",
                operational_status="published",
            )
            db_session.commit()

            with patch(
                "tasks.data_import.odpt.import_odpt_feeds.requests.Session",
                return_value=_FakeSessionDryRun(),
            ), patch(
                "tasks.data_import.odpt.import_odpt_feeds.REQUEST_TIMEOUT_S", 0.01
            ), patch(
                "tasks.data_import.data_import_utils.trigger_dataset_download",
                mock_trigger,
            ), patch(
                "tasks.data_import.data_import_utils.create_web_revalidation_task",
                mock_revalidate,
            ):
                result = import_odpt_handler({"dry_run": True})

            # The summary still reports what *would* have happened, including the
            # would-be deprecations. Not an exact count: the shared test DB may hold
            # stray odpt-* rows from other tests, which the sweep also sees.
            self.assertEqual(result["message"], "Dry run: no DB writes performed.")
            self.assertEqual(result["created_gtfs"], 1)
            self.assertEqual(result["updated_gtfs"], 0)
            self.assertEqual(result["created_gtfs_rt"], 2)
            self.assertEqual(result["updated_gtfs_rt"], 0)
            self.assertEqual(result["linked_refs"], 2)
            self.assertEqual(result["total_processed_items"], 1)
            self.assertEqual(result["params"], {"dry_run": True})
            self.assertGreaterEqual(result["deprecated"], 1)

            # ...but nothing was actually written to the database.
            db_session.expire_all()
            sched = (
                db_session.query(Gtfsfeed)
                .filter(Gtfsfeed.stable_id == "odpt-DryRunOrg-dry_run_dataset")
                .first()
            )
            self.assertIsNone(sched)

            rt_feeds = (
                db_session.query(Gtfsrealtimefeed)
                .filter(
                    Gtfsrealtimefeed.stable_id.like("odpt-DryRunOrg-dry_run_dataset-%")
                )
                .all()
            )
            self.assertEqual(rt_feeds, [])

            # Crucially, the stale feed was NOT actually deprecated by the dry run.
            stale = db_session.query(Feed).filter(Feed.stable_id == stale_id).one()
            self.assertEqual(
                (stale.status, stale.operational_status), ("active", "published")
            )

            # Side effects must not fire either -- they're both dry_run-gated too.
            mock_trigger.assert_not_called()
            mock_revalidate.assert_not_called()
        finally:
            _delete_feeds_like(db_session, "odpt-DryRunStaleOrg-%")

    @with_db_session(db_url=default_db_url)
    def test_reappeared_feed_is_reactivated(self, db_session: Session):
        """
        A feed previously swept as stale, now advertised again with byte-identical
        fields, must be restored to active/published.

        This is the case a naive implementation silently misses: the schedule
        fingerprint matches exactly (it covers only API-persisted fields, not
        status/operational_status), so without the reactivation check in
        _process_feed the importer takes the "no change detected" early return,
        never reaches _update_common_feed_fields, and the feed stays hidden forever.
        """
        stable_id = "odpt-ReactOrg-react_dataset"
        try:
            _seed_feed(
                db_session,
                Gtfsfeed,
                stable_id,
                "gtfs",
                # Identical to what _FakeSessionReactivate will report.
                feed_name="リアクトデータセット",
                provider="リアクト組織",
                producer_url=GTFS_ENDPOINT_TMPL.format("ReactOrg", "react_dataset"),
                license_url=CC0_URL,
                status="deprecated",
                operational_status="unpublished",
            )
            db_session.commit()

            with patch(
                "tasks.data_import.odpt.import_odpt_feeds.requests.Session",
                return_value=_FakeSessionReactivate(),
            ), patch(
                "tasks.data_import.odpt.import_odpt_feeds.REQUEST_TIMEOUT_S", 0.01
            ), patch(
                # Not a sweep test; keep it off other tests' rows.
                "tasks.data_import.odpt.import_odpt_feeds.deprecate_stale_feeds",
                MagicMock(return_value=[]),
            ), patch(
                "tasks.data_import.data_import_utils.trigger_dataset_download",
                MagicMock(),
            ), patch(
                "tasks.data_import.data_import_utils.create_web_revalidation_task",
                MagicMock(),
            ), patch.dict(
                os.environ, {"ENVIRONMENT": "test"}, clear=False
            ):
                result = import_odpt_handler({"dry_run": False})

            # Counted as an update, not a creation -- the row already existed.
            self.assertEqual(result["created_gtfs"], 0)
            self.assertEqual(result["updated_gtfs"], 1)

            db_session.expire_all()
            feed = db_session.query(Feed).filter(Feed.stable_id == stable_id).one()
            self.assertEqual(
                (feed.status, feed.operational_status), ("active", "published")
            )
        finally:
            _delete_feeds_like(db_session, "odpt-ReactOrg-%")

    @with_db_session(db_url=default_db_url)
    def test_withdrawn_rt_subfeed_is_deprecated_without_touching_siblings(
        self, db_session: Session
    ):
        """
        End-to-end proof the real (unmocked) sweep runs, at RT granularity: when only
        the alert URL is withdrawn, just the `-sa` sub-feed is deprecated while the
        schedule feed and its tu/vp siblings stay published.

        NOTE: this test cannot mock the sweep, so it also deprecates any unrelated
        odpt-* rows other tests left in the shared session-scoped test DB. That's
        harmless here (each test asserts its own rows) but it's why this test checks
        specific rows rather than an exact result["deprecated"] count.
        """
        base = "odpt-RtGranOrg-rt_gran_dataset"
        try:
            _seed_feed(
                db_session,
                Gtfsfeed,
                base,
                "gtfs",
                feed_name="RTグランデータセット",
                provider="RTグラン組織",
                producer_url=GTFS_ENDPOINT_TMPL.format("RtGranOrg", "rt_gran_dataset"),
                license_url=CC0_URL,
                status="active",
                operational_status="published",
            )
            for entity_type, url in (
                ("tu", _FakeSessionRtGranularity.TU_URL),
                ("vp", _FakeSessionRtGranularity.VP_URL),
                ("sa", "https://rt.example/rtgran/sa.pb"),
            ):
                _seed_feed(
                    db_session,
                    Gtfsrealtimefeed,
                    f"{base}-{entity_type}",
                    "gtfs_rt",
                    producer_url=url,
                    status="active",
                    operational_status="published",
                )
            db_session.commit()

            with patch(
                "tasks.data_import.odpt.import_odpt_feeds.requests.Session",
                return_value=_FakeSessionRtGranularity(),
            ), patch(
                "tasks.data_import.odpt.import_odpt_feeds.REQUEST_TIMEOUT_S", 0.01
            ), patch(
                "tasks.data_import.data_import_utils.trigger_dataset_download",
                MagicMock(),
            ), patch(
                "tasks.data_import.data_import_utils.create_web_revalidation_task",
                MagicMock(),
            ), patch.dict(
                os.environ, {"ENVIRONMENT": "test"}, clear=False
            ):
                result = import_odpt_handler({"dry_run": False})

            self.assertGreaterEqual(result["deprecated"], 1)

            db_session.expire_all()
            still_published = (base, f"{base}-tu", f"{base}-vp")
            for stable_id in still_published:
                feed = db_session.query(Feed).filter(Feed.stable_id == stable_id).one()
                self.assertEqual(
                    (feed.status, feed.operational_status),
                    ("active", "published"),
                    f"{stable_id} should still be published",
                )

            withdrawn = (
                db_session.query(Feed).filter(Feed.stable_id == f"{base}-sa").one()
            )
            self.assertEqual(
                (withdrawn.status, withdrawn.operational_status),
                ("deprecated", "unpublished"),
            )
        finally:
            _delete_feeds_like(db_session, f"{base}%")

    @with_db_session(db_url=default_db_url)
    def test_empty_fetch_does_not_deprecate_the_whole_catalog(
        self, db_session: Session
    ):
        """
        A successful-but-empty response must NOT be treated as "every feed was
        withdrawn". Without the `if feeds_list:` guard this is catastrophic rather
        than merely wrong: ~stable_id.in_(empty set) compiles to an always-true
        predicate, so the sweep would deprecate every odpt-* feed in one run.
        """
        stable_id = "odpt-EmptyFetchOrg-survivor_dataset"
        try:
            _seed_feed(
                db_session,
                Gtfsfeed,
                stable_id,
                "gtfs",
                status="active",
                operational_status="published",
            )
            db_session.commit()

            with patch(
                "tasks.data_import.odpt.import_odpt_feeds.requests.Session",
                return_value=_FakeSessionEmpty(),
            ), patch(
                "tasks.data_import.odpt.import_odpt_feeds.REQUEST_TIMEOUT_S", 0.01
            ), patch(
                "tasks.data_import.data_import_utils.trigger_dataset_download",
                MagicMock(),
            ), patch(
                "tasks.data_import.data_import_utils.create_web_revalidation_task",
                MagicMock(),
            ), patch.dict(
                os.environ, {"ENVIRONMENT": "test"}, clear=False
            ):
                result = import_odpt_handler({"dry_run": False})

            self.assertEqual(result["total_processed_items"], 0)
            self.assertEqual(result["deprecated"], 0)

            db_session.expire_all()
            survivor = db_session.query(Feed).filter(Feed.stable_id == stable_id).one()
            self.assertEqual(
                (survivor.status, survivor.operational_status), ("active", "published")
            )
        finally:
            _delete_feeds_like(db_session, "odpt-EmptyFetchOrg-%")

    @with_db_session(db_url=default_db_url)
    def test_import_http_failure_graceful(self, db_session: Session):
        with patch(
            "tasks.data_import.odpt.import_odpt_feeds.requests.Session",
            return_value=_FakeSessionError(),
        ), patch("tasks.data_import.odpt.import_odpt_feeds.REQUEST_TIMEOUT_S", 0.01):
            out = import_odpt_handler({"dry_run": True})

        self.assertEqual(out["message"], "Failed to fetch ODPT feeds.")
        self.assertIn("error", out)
        self.assertEqual(out["created_gtfs"], 0)
        self.assertEqual(out["updated_gtfs"], 0)
        self.assertEqual(out["created_gtfs_rt"], 0)
        self.assertEqual(out["updated_gtfs_rt"], 0)
        # A failed fetch must never be read as "everything was withdrawn".
        self.assertEqual(out["deprecated"], 0)
        self.assertEqual(out["linked_refs"], 0)
        self.assertEqual(out["total_processed_items"], 0)


if __name__ == "__main__":
    unittest.main()
