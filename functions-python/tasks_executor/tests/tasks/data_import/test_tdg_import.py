import os
import unittest
import uuid
from typing import Any, Dict, Optional
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsfeed,
    Gtfsrealtimefeed,
)
from tasks.data_import.transportdatagouv.import_tdg_feeds import (
    import_tdg_handler,
    _get_license_url,
    _probe_head_format,
    _get_entity_types_from_resource,
)
from test_shared.test_utils.database_utils import default_db_url


class _FakeResponse:
    def __init__(
        self,
        body: Dict[str, Any] | None = None,
        status: int = 200,
        headers: Dict[str, str] | None = None,
    ):
        self._body = body or {}
        self.status_code = status
        self.headers = headers or {"Content-Type": "application/json; charset=utf-8"}

    def json(self):
        return self._body

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSessionOK:
    """
    Fake HTTP session for TDG:
      - GET on TDG_DATASETS_URL returns 1 dataset with:
          * 1 valid GTFS resource (zip)
          * 1 RT resource with trip_updates + vehicle_positions
      - HEAD on the GTFS URL returns a zip content-type
    """

    TDG_DATASETS_URL = "https://transport.data.gouv.fr/api/datasets?format=gtfs"

    def get(self, url, timeout=60, headers=None):
        if url == self.TDG_DATASETS_URL:
            return _FakeResponse(
                [
                    {
                        "id": "ds1",
                        "title": "Dataset One",
                        "publisher": {"name": "TDG Org"},
                        "licence": "odc-odbl",
                        "covered_area": [
                            {
                                "type": "pays",
                                "nom": "France",
                                "insee": "FR",
                            },
                            {
                                "type": "region",
                                "nom": "Île-de-France",
                                "insee": "11",
                            },
                        ],
                        "resources": [
                            {
                                "id": "res-static1",
                                "title": "Static GTFS",
                                "format": "GTFS",
                                "url": "https://tdg.example/gtfs1.zip",
                                "metadata": {"end_date": "2999-12-31"},
                            },
                            {
                                "id": "res-rt1",
                                "title": "RT feed",
                                "format": "gtfs-rt",
                                "url": "https://tdg.example/rt1.pb",
                                "features": ["trip_updates", "vehicle_positions"],
                            },
                        ],
                    }
                ]
            )
        return _FakeResponse({}, status=404)

    def head(self, url, allow_redirects=True, timeout=15):
        # Treat the GTFS URL as a valid zip; everything else unknown
        if url == "https://tdg.example/gtfs1.zip":
            return _FakeResponse(
                status=200,
                headers={"Content-Type": "application/zip"},
            )
        return _FakeResponse(
            status=200,
            headers={"Content-Type": "application/octet-stream"},
        )


class _FakeSessionSeasonal:
    """
    One dataset with a single GTFS resource, under its own resource id so the rows it
    touches never overlap the happy-path test's. Used by the `seasonal` preservation
    tests: the dataset title differs from the stale one seeded into the DB, so the
    schedule fingerprint cannot match and the importer is forced down its update path
    instead of the "no change detected" early return.
    """

    TDG_DATASETS_URL = "https://transport.data.gouv.fr/api/datasets?format=gtfs"
    GTFS_URL = "https://tdg.example/seasonal.zip"

    def get(self, url, timeout=60, headers=None):
        if url == self.TDG_DATASETS_URL:
            return _FakeResponse(
                [
                    {
                        "id": "ds-seasonal",
                        "title": "Seasonal Dataset",
                        "publisher": {"name": "TDG Seasonal Org"},
                        "licence": "odc-odbl",
                        "resources": [
                            {
                                "id": "res-seasonal",
                                "title": "Static GTFS",
                                "format": "GTFS",
                                "url": self.GTFS_URL,
                                "metadata": {"end_date": "2999-12-31"},
                            }
                        ],
                    }
                ]
            )
        return _FakeResponse({}, status=404)

    def head(self, url, allow_redirects=True, timeout=15):
        if url == self.GTFS_URL:
            return _FakeResponse(
                status=200, headers={"Content-Type": "application/zip"}
            )
        return _FakeResponse(
            status=200, headers={"Content-Type": "application/octet-stream"}
        )


class _FakeSessionError:
    """
    Fake HTTP session that always fails on GET.
    Used to test graceful handling of HTTP errors at the list-fetch level.
    """

    def get(self, url, timeout=60):
        raise RuntimeError("network down")

    def head(self, url, allow_redirects=True, timeout=15):
        raise RuntimeError("network down")


# ─────────────────────────────────────────────────────────────────────────────
# Helper function tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTDGHelpers(unittest.TestCase):
    def test_get_license_url_mapping_and_unknown(self):
        # Known (case-insensitive)
        self.assertEqual(
            _get_license_url("odc-odbl"),
            "https://opendatacommons.org/licenses/odbl/1.0/",
        )
        self.assertEqual(
            _get_license_url("ODC-ODBL"),
            "https://opendatacommons.org/licenses/odbl/1.0/",
        )

        # Unknown and None
        self.assertIsNone(_get_license_url("some-other-license"))
        self.assertIsNone(_get_license_url(None))

    def test_probe_head_format_detects_zip_and_csv(self):
        # Fake session to drive _probe_head_format
        sess = MagicMock()

        zip_resp = _FakeResponse(
            status=200, headers={"Content-Type": "application/zip"}
        )
        csv_resp = _FakeResponse(
            status=200, headers={"Content-Type": "text/csv; charset=utf-8"}
        )

        sess.head.side_effect = [zip_resp, csv_resp]

        status, ctype, detected = _probe_head_format(
            sess, "https://example.com/file.zip"
        )
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "application/zip")
        self.assertEqual(detected, "zip")

        status2, ctype2, detected2 = _probe_head_format(
            sess, "https://example.com/file.csv"
        )
        self.assertEqual(status2, 200)
        self.assertTrue(ctype2.startswith("text/csv"))
        self.assertEqual(detected2, "csv")

    def test_get_entity_types_from_resource(self):
        resource = {
            "features": [
                "trip_updates",
                "vehicle_positions",
                "SERVICE_ALERTS",
                "something_else",
            ]
        }
        # Expected mapping via ENTITY_TYPES_MAP
        entity_types = _get_entity_types_from_resource(resource)
        self.assertEqual(sorted(entity_types), ["sa", "tu", "vp"])


# ─────────────────────────────────────────────────────────────────────────────
# Import tests
# ─────────────────────────────────────────────────────────────────────────────


class TestImportTDG(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def test_import_creates_gtfs_and_rt(self, db_session: Session):
        """
        Happy-path test:
          - 1 dataset with 1 GTFS + 1 RT resource
          - GTFS is created
          - RT is created and linked to schedule
          - trigger_dataset_download is called once (for the new GTFS feed)
        """
        mock_trigger = MagicMock()

        with patch(
            "tasks.data_import.transportdatagouv.import_tdg_feeds.requests.Session",
            return_value=_FakeSessionOK(),
        ), patch(
            "tasks.data_import.transportdatagouv.import_tdg_feeds.REQUEST_TIMEOUT_S",
            0.01,
        ), patch(
            # commit_changes (and the side effects it triggers) now lives in
            # data_import_utils, shared with jbda/odpt -- patch it there, not on
            # this module, since that's where the name is looked up at call time.
            "tasks.data_import.data_import_utils.trigger_dataset_download",
            mock_trigger,
        ), patch.dict(
            os.environ,
            {"COMMIT_BATCH_SIZE": "1", "ENVIRONMENT": "test"},
            clear=False,
        ):
            result = import_tdg_handler({"dry_run": False})

        # Summary: we expect 1 GTFS + 1 RT, processed 2 items.
        self.assertEqual(
            result,
            {
                "message": "TDG import executed successfully.",
                "created_gtfs": 1,
                "updated_gtfs": 0,
                "created_rt": 1,
                "total_processed_items": 2,
                "params": {"dry_run": False},
            },
        )

        # Check the schedule feed in DB
        sched: Optional[Gtfsfeed] = (
            db_session.query(Gtfsfeed)
            .filter(Gtfsfeed.stable_id == "tdg-res-static1")
            .first()
        )
        self.assertIsNotNone(sched)
        sched = db_session.merge(sched)  # attach to session for relationships

        self.assertEqual(sched.feed_name, "Dataset One")
        self.assertEqual(sched.provider, "TDG Org")
        self.assertEqual(sched.producer_url, "https://tdg.example/gtfs1.zip")
        self.assertEqual(
            sched.license_url,
            "https://opendatacommons.org/licenses/odbl/1.0/",
        )
        self.assertEqual(sched.status, "active")
        self.assertEqual(sched.operational_status, "published")

        # Check RT feed in DB and its links
        rt: Optional[Gtfsrealtimefeed] = (
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == "tdg-res-rt1")
            .first()
        )
        self.assertIsNotNone(rt)
        rt = db_session.merge(rt)

        self.assertEqual(rt.producer_url, "https://tdg.example/rt1.pb")

        # Entity types should come from features ["trip_updates","vehicle_positions"]
        et_names = sorted(et.name for et in rt.entitytypes)
        self.assertEqual(et_names, ["tu", "vp"])

        # RT should be linked to the schedule feed
        rt_sched_ids = [f.id for f in rt.gtfs_feeds]
        self.assertEqual(rt_sched_ids, [sched.id])

        # trigger_dataset_download should have been called once for the new GTFS feed
        mock_trigger.assert_called_once()
        called_args = mock_trigger.call_args[0]
        self.assertGreaterEqual(len(called_args), 2)
        detached_feed = called_args[0]
        merged_feed = db_session.merge(detached_feed)
        self.assertEqual(getattr(merged_feed, "stable_id", None), "tdg-res-static1")
        self.assertIsInstance(called_args[1], str)  # execution_id

    @with_db_session(db_url=default_db_url)
    def test_import_http_failure_graceful(self, db_session: Session):
        """
        If the initial TDG datasets fetch fails, the handler should return
        a failure summary but not raise.
        """
        with patch(
            "tasks.data_import.transportdatagouv.import_tdg_feeds.requests.Session",
            return_value=_FakeSessionError(),
        ), patch(
            "tasks.data_import.transportdatagouv.import_tdg_feeds.REQUEST_TIMEOUT_S",
            0.01,
        ):
            out = import_tdg_handler({"dry_run": True})

        self.assertEqual(out["message"], "Failed to fetch TDG datasets.")
        self.assertIn("error", out)
        self.assertEqual(out["created_gtfs"], 0)
        self.assertEqual(out["updated_gtfs"], 0)
        self.assertEqual(out["created_rt"], 0)
        self.assertEqual(out["total_processed_items"], 0)

    SEASONAL_STABLE_ID = "tdg-res-seasonal"

    def _run_seasonal_import(self):
        """Run the importer against _FakeSessionSeasonal with side effects stubbed out."""
        with patch(
            "tasks.data_import.transportdatagouv.import_tdg_feeds.requests.Session",
            return_value=_FakeSessionSeasonal(),
        ), patch(
            "tasks.data_import.transportdatagouv.import_tdg_feeds.REQUEST_TIMEOUT_S",
            0.01,
        ), patch(
            "tasks.data_import.data_import_utils.trigger_dataset_download",
            MagicMock(),
        ), patch(
            "tasks.data_import.data_import_utils.create_web_revalidation_task",
            MagicMock(),
        ), patch(
            # This test is not about the stale sweep. Stub it so it cannot deprecate the
            # tdg- rows the happy-path test committed into the shared session-scoped DB.
            "tasks.data_import.transportdatagouv.import_tdg_feeds._deprecate_stale_feeds",
            MagicMock(return_value=[]),
        ), patch.dict(
            os.environ,
            {"COMMIT_BATCH_SIZE": "1", "ENVIRONMENT": "test"},
            clear=False,
        ):
            return import_tdg_handler({"dry_run": False})

    @with_db_session(db_url=default_db_url)
    def test_seasonal_survives_reimport(self, db_session: Session):
        """`seasonal` is operator-owned, so a re-import must leave it alone (issue #1798).

        No TDG payload carries a seasonality signal, so if the importer ever wrote the
        column the flag would be cleared on the next monthly run and the feed would silently
        start failing the rolling 7-day coverage criterion again.
        """
        try:
            db_session.add(
                Gtfsfeed(
                    id=str(uuid.uuid4()),
                    stable_id=self.SEASONAL_STABLE_ID,
                    data_type="gtfs",
                    # Stale on purpose: feed_name is part of the schedule fingerprint, so
                    # this forces the update path. Without it the importer short-circuits
                    # on "no change detected" and the test would pass vacuously.
                    feed_name="Stale dataset title",
                    seasonal=True,
                )
            )
            db_session.commit()

            self._run_seasonal_import()

            db_session.expire_all()
            feed = (
                db_session.query(Gtfsfeed)
                .filter(Gtfsfeed.stable_id == self.SEASONAL_STABLE_ID)
                .one()
            )
            # Proves the importer really rewrote this row, so the assertion below is real.
            self.assertEqual(feed.feed_name, "Seasonal Dataset")
            self.assertTrue(feed.seasonal)
        finally:
            db_session.query(Feed).filter(
                Feed.stable_id == self.SEASONAL_STABLE_ID
            ).delete(synchronize_session=False)
            db_session.commit()

    @with_db_session(db_url=default_db_url)
    def test_seasonal_survives_data_type_change(self, db_session: Session):
        """A GTFS-RT -> GTFS flip deletes and recreates the row; `seasonal` must carry over.

        _delete_and_recreate_feed_if_type_changed is the one path in any importer that drops
        operator-set columns, because the new row is built from scratch.
        """
        try:
            db_session.add(
                Gtfsrealtimefeed(
                    id=str(uuid.uuid4()),
                    stable_id=self.SEASONAL_STABLE_ID,
                    data_type="gtfs_rt",
                    feed_name="Stale dataset title",
                    seasonal=True,
                )
            )
            db_session.commit()

            self._run_seasonal_import()

            db_session.expire_all()
            feed = (
                db_session.query(Feed)
                .filter(Feed.stable_id == self.SEASONAL_STABLE_ID)
                .one()
            )
            # The row was recreated as a schedule feed...
            self.assertEqual(feed.data_type, "gtfs")
            # ...and the operator-set flag survived the delete/recreate.
            self.assertTrue(feed.seasonal)
        finally:
            db_session.query(Feed).filter(
                Feed.stable_id == self.SEASONAL_STABLE_ID
            ).delete(synchronize_session=False)
            db_session.commit()


if __name__ == "__main__":
    unittest.main()
