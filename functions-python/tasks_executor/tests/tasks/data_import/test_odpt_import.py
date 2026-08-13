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
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from test_shared.test_utils.database_utils import default_db_url
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsrealtimefeed

from tasks.data_import.odpt.import_odpt_feeds import (
    import_odpt_handler,
    _get_license_url,
)


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


class _FakeSessionError:
    def get(self, url, timeout=60):
        raise RuntimeError("network down")


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

        # The summary still reports what *would* have happened...
        self.assertEqual(
            {
                "message": "Dry run: no DB writes performed.",
                "created_gtfs": 1,
                "updated_gtfs": 0,
                "created_gtfs_rt": 2,
                "updated_gtfs_rt": 0,
                "linked_refs": 2,
                "total_processed_items": 1,
                "params": {"dry_run": True},
            },
            result,
        )

        # ...but nothing was actually written to the database.
        sched = (
            db_session.query(Gtfsfeed)
            .filter(Gtfsfeed.stable_id == "odpt-DryRunOrg-dry_run_dataset")
            .first()
        )
        self.assertIsNone(sched)

        rt_feeds = (
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id.like("odpt-DryRunOrg-dry_run_dataset-%"))
            .all()
        )
        self.assertEqual(rt_feeds, [])

        # Side effects must not fire either -- they're both dry_run-gated too.
        mock_trigger.assert_not_called()
        mock_revalidate.assert_not_called()

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
        self.assertEqual(out["linked_refs"], 0)
        self.assertEqual(out["total_processed_items"], 0)


if __name__ == "__main__":
    unittest.main()
