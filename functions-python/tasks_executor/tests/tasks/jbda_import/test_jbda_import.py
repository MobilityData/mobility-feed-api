import sys
import types
import unittest
from typing import Any, Dict, List
from unittest.mock import patch

from sqlalchemy.orm import Session

from test_shared.test_utils.database_utils import default_db_url
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsrealtimefeed,
    Entitytype,
    Feedrelatedlink,
)

from tasks.jbda_import.import_jbda_feeds import (
    import_jbda_handler,
    get_gtfs_file_url,
    _choose_gtfs_file,
)


class _FakeResponse:
    def __init__(
        self,
        body: Dict[str, Any] | None,
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
    Returns a feeds list with 3 items:
      - feed1: valid (creates 1 GTFS + 2 RT and 1 related link for next_1)
      - feed2: discontinued -> skipped
      - feed3: missing gtfs_url in detail -> skipped
    """

    FEEDS_URL = "https://api.gtfs-data.jp/v2/feeds"
    DETAIL_TMPL = "https://api.gtfs-data.jp/v2/organizations/{org_id}/feeds/{feed_id}"

    def get(self, url, timeout=60):
        # feeds index
        if url == self.FEEDS_URL:
            return _FakeResponse(
                {
                    "body": [
                        {
                            "organization_id": "org1",
                            "feed_id": "feed1",
                            "organization_name": "Org A",
                            "organization_email": "contact@orga.example",
                            "feed_pref_id": 1,
                            "feed_memo": "memo1",
                        },
                        {
                            "organization_id": "org2",
                            "feed_id": "feed2",
                            "is_discontinued": True,
                            "organization_name": "Org B",
                            "organization_email": "b@b.example",
                            "feed_pref_id": 2,
                        },
                        {
                            "organization_id": "org3",
                            "feed_id": "feed3",
                            "organization_name": "Org C",
                            "organization_email": "c@c.example",
                            "feed_pref_id": 3,
                        },
                    ]
                }
            )

        # details for feed1
        if url == self.DETAIL_TMPL.format(org_id="org1", feed_id="feed1"):
            return _FakeResponse(
                {
                    "body": {
                        "feed_name": "Feed One",
                        "feed_license_url": "https://license.example/1",
                        "gtfs_files": [
                            {
                                "rid": "current",
                                "gtfs_file_uid": "u1",
                                "gtfs_url": "https://gtfs.example/one.zip",
                                "stop_url": "https://gtfs.example/one-stops.txt",
                            },
                            {
                                "rid": "next_1",
                                "gtfs_file_uid": "u2",
                                "gtfs_url": "https://gtfs.example/one-next.zip",
                            },
                        ],
                        "real_time": {
                            "trip_update_url": "https://rt.example/one/tu.pb",
                            "vehicle_position_url": "https://rt.example/one/vp.pb",
                            # "alert_url": missing on purpose
                        },
                    }
                }
            )

        # details for feed2 (won't be called, discontinued)
        if url == self.DETAIL_TMPL.format(org_id="org2", feed_id="feed2"):
            return _FakeResponse({"body": {}}, 404)

        # details for feed3 (no gtfs_url -> skipped)
        if url == self.DETAIL_TMPL.format(org_id="org3", feed_id="feed3"):
            return _FakeResponse(
                {
                    "body": {
                        "feed_name": "Feed Three",
                        "gtfs_files": [
                            {"rid": "current", "gtfs_file_uid": "u3"}  # no urls
                        ],
                        "real_time": {},
                    }
                }
            )

        return _FakeResponse({}, 404)


class _FakeSessionError:
    def get(self, url, timeout=60):
        raise RuntimeError("network down")


class TestHelpers(unittest.TestCase):
    def test_choose_gtfs_file(self):
        files = [
            {"rid": "prev_1", "gtfs_url": "A"},
            {"rid": "current", "gtfs_url": "B"},
            {"rid": "next_1", "gtfs_url": "C"},
        ]
        self.assertEqual(_choose_gtfs_file(files, "current")["gtfs_url"], "B")
        self.assertIsNone(_choose_gtfs_file(files, "nope"))

    def test_get_gtfs_file_url(self):
        detail = {
            "gtfs_files": [
                {"rid": "current", "gtfs_url": "CUR.zip", "stop_url": "CUR-stops.txt"},
                {"rid": "next_1", "gtfs_url": "N1.zip"},
            ]
        }
        self.assertEqual(
            get_gtfs_file_url(detail, rid="current", kind="gtfs_url"), "CUR.zip"
        )
        self.assertEqual(
            get_gtfs_file_url(detail, rid="current", kind="stop_url"), "CUR-stops.txt"
        )
        self.assertEqual(
            get_gtfs_file_url(detail, rid="next_1", kind="gtfs_url"), "N1.zip"
        )
        self.assertIsNone(get_gtfs_file_url(detail, rid="next_2", kind="gtfs_url"))


class _RequestsModule(types.ModuleType):
    def __init__(self, session_cls):
        super().__init__("requests")
        self._session_cls = session_cls

    class _SessionWrapper:
        def __init__(self, inner):
            self._inner = inner

        def get(self, *a, **k):
            return self._inner.get(*a, **k)

    def Session(self):
        return self._SessionWrapper(self._session_cls())


class TestImportJBDA(unittest.TestCase):
    def _patch_requests(self, session_cls):
        fake_requests = _RequestsModule(session_cls)
        return patch.dict(sys.modules, {"requests": fake_requests}, clear=False)

    @with_db_session(db_url=default_db_url)
    def test_import_creates_gtfs_rt_and_related_links(self, db_session: Session):
        with patch(
            "tasks.jbda_import.import_jbda_feeds.requests.Session",
            return_value=_FakeSessionOK(),
        ), patch("tasks.jbda_import.import_jbda_feeds.REQUEST_TIMEOUT_S", 0.01):
            result = import_jbda_handler({"dry_run": False})

        # Summary checks
        self.assertEqual(
            {
                "message": "JBDA import executed successfully.",
                "created_gtfs": 1,
                "updated_gtfs": 0,
                "created_rt": 2,
                "linked_refs": 2,  # one per RT link established (tu + vp)
                "total_processed_items": 1,
                "params": {"dry_run": False},
            },
            result,
        )

        # DB checks for GTFS feed
        sched = (
            db_session.query(Gtfsfeed)
            .filter(Gtfsfeed.stable_id == "jbda-feed1")
            .first()
        )
        self.assertIsNotNone(sched)
        self.assertEqual(sched.feed_name, "Feed One")
        self.assertEqual(sched.producer_url, "https://gtfs.example/one.zip")
        # Related links (only next_1 exists in detail)
        links: List[Feedrelatedlink] = list(sched.feedrelatedlinks)
        codes = {link.code for link in links}
        self.assertIn("next_1", codes)
        # URL for next_1 correct
        next1 = next(link for link in links if link.code == "next_1")
        self.assertEqual(next1.url, "https://gtfs.example/one-next.zip")

        # DB checks for RT feeds
        tu = (
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == "jbda-feed1-tu")
            .first()
        )
        vp = (
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == "jbda-feed1-vp")
            .first()
        )
        self.assertIsNotNone(tu)
        self.assertIsNotNone(vp)
        # Each RT has single entity type and back-link to schedule
        self.assertEqual(len(tu.entitytypes), 1)
        self.assertEqual(len(vp.entitytypes), 1)
        tu_et_name = db_session.query(Entitytype).get(tu.entitytypes[0].name).name
        vp_et_name = db_session.query(Entitytype).get(vp.entitytypes[0].name).name
        self.assertEqual(tu_et_name, "tu")
        self.assertEqual(vp_et_name, "vp")
        self.assertEqual([f.id for f in tu.gtfs_feeds], [sched.id])
        self.assertEqual([f.id for f in vp.gtfs_feeds], [sched.id])
        # RT producer_url set from RT endpoint
        self.assertEqual(tu.producer_url, "https://rt.example/one/tu.pb")
        self.assertEqual(vp.producer_url, "https://rt.example/one/vp.pb")

    @with_db_session(db_url=default_db_url)
    def test_import_http_failure_graceful(self, db_session: Session):
        with patch(
            "tasks.jbda_import.import_jbda_feeds.requests.Session",
            return_value=_FakeSessionError(),
        ), patch("tasks.jbda_import.import_jbda_feeds.REQUEST_TIMEOUT_S", 0.01):
            out = import_jbda_handler({"dry_run": True})

        self.assertEqual(out["message"], "Failed to fetch JBDA feeds.")
        self.assertIn("error", out)
        self.assertEqual(out["created_gtfs"], 0)
        self.assertEqual(out["updated_gtfs"], 0)
        self.assertEqual(out["created_rt"], 0)
        self.assertEqual(out["linked_refs"], 0)
        self.assertEqual(out["total_processed_items"], 0)


if __name__ == "__main__":
    unittest.main()
