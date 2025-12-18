import os
import unittest
from typing import Any, Dict, Optional
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
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
            "tasks.data_import.transportdatagouv.import_tdg_feeds.trigger_dataset_download",
            mock_trigger,
        ), patch.dict(
            os.environ,
            {"COMMIT_BATCH_SIZE": "1", "ENV": "test"},
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


if __name__ == "__main__":
    unittest.main()
