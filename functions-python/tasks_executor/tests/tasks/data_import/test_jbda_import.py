import os
import json
import unittest
from typing import Any, Dict, List
from unittest.mock import patch

from sqlalchemy.orm import Session

from test_shared.test_utils.database_utils import default_db_url
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsrealtimefeed,
    Feedrelatedlink,
)

from tasks.data_import.jbda.import_jbda_feeds import (
    import_jbda_handler,
    get_gtfs_file_url,
)


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
    Returns a feeds list with 3 items:
      - feed1: valid (creates 1 GTFS + 2 RT and 1 related link for next_1)
      - feed2: discontinued -> skipped
      - feed3: missing valid HEAD for current -> skipped
    """

    FEEDS_URL = "https://api.gtfs-data.jp/v2/feeds"
    DETAIL_TMPL = "https://api.gtfs-data.jp/v2/organizations/{org_id}/feeds/{feed_id}"

    def get(self, url, timeout=60):
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

        if url == self.DETAIL_TMPL.format(org_id="org1", feed_id="feed1"):
            return _FakeResponse(
                {
                    "body": {
                        # include org/feed ids so get_gtfs_file_url can build URL
                        "organization_id": "org1",
                        "feed_id": "feed1",
                        "feed_name": "Feed One",
                        "feed_license_url": "https://license.example/1",
                        # gtfs_files not used by get_gtfs_file_url anymore, but harmless to keep
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

        if url == self.DETAIL_TMPL.format(org_id="org3", feed_id="feed3"):
            return _FakeResponse(
                {
                    "body": {
                        "organization_id": "org3",
                        "feed_id": "feed3",
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


class _FakeFuture:
    def __init__(self):
        self._callbacks = []

    def add_done_callback(self, cb):
        try:
            cb(self)
        except Exception:
            pass

    def result(self, timeout=None):
        return None


class _FakePublisher:
    def __init__(self):
        self.published = []  # list of tuples (topic_path, data_bytes)

    def topic_path(self, project_id, topic_name):
        return f"projects/{project_id}/topics/{topic_name}"

    def publish(self, topic_path, data: bytes):
        self.published.append((topic_path, data))
        return _FakeFuture()


# ─────────────────────────────────────────────────────────────────────────────
# Helper function tests
# ─────────────────────────────────────────────────────────────────────────────


class TestHelpers(unittest.TestCase):
    def test_get_gtfs_file_url_head_success_and_missing(self):
        # detail now needs org/feed ids
        detail = {"organization_id": "orgX", "feed_id": "feedX"}

        # Construct the URLs the function will probe
        base = (
            "https://api.gtfs-data.jp/v2/organizations/orgX/feeds/feedX/files/feed.zip"
        )
        url_current = f"{base}?rid=current"
        url_next1 = f"{base}?rid=next_1"
        url_next2 = f"{base}?rid=next_2"

        def _head_side_effect(url, allow_redirects=True, timeout=15):
            if url in (url_current, url_next1):
                return _FakeResponse(status=200)
            if url == url_next2:
                return _FakeResponse(status=404)
            return _FakeResponse(status=404)

        with patch(
            "tasks.data_import.jbda.import_jbda_feeds.requests.head",
            side_effect=_head_side_effect,
        ):
            self.assertEqual(get_gtfs_file_url(detail, rid="current"), url_current)
            self.assertEqual(get_gtfs_file_url(detail, rid="next_1"), url_next1)
            self.assertIsNone(get_gtfs_file_url(detail, rid="next_2"))


# ─────────────────────────────────────────────────────────────────────────────
# Import tests
# ─────────────────────────────────────────────────────────────────────────────


class TestImportJBDA(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def test_import_creates_gtfs_rt_and_related_links(self, db_session: Session):
        fake_pub = _FakePublisher()

        # The importer will call HEAD on these URLs for org1/feed1
        base = (
            "https://api.gtfs-data.jp/v2/organizations/org1/feeds/feed1/files/feed.zip"
        )
        url_current = f"{base}?rid=current"
        url_next1 = f"{base}?rid=next_1"

        def _head_side_effect(url, allow_redirects=True, timeout=15):
            # succeed for current and next_1 (feed1)
            if url in (url_current, url_next1):
                return _FakeResponse(status=200)
            # fail for anything else (e.g., feed3 current)
            return _FakeResponse(status=404)

        with patch(
            "tasks.data_import.jbda.import_jbda_feeds.requests.Session",
            return_value=_FakeSessionOK(),
        ), patch(
            "tasks.data_import.jbda.import_jbda_feeds.requests.head",
            side_effect=_head_side_effect,
        ), patch(
            "tasks.data_import.jbda.import_jbda_feeds.REQUEST_TIMEOUT_S", 0.01
        ), patch(
            "tasks.data_import.jbda.import_jbda_feeds.pubsub_v1.PublisherClient",
            return_value=fake_pub,
        ), patch(
            "tasks.data_import.data_import_utils.PROJECT_ID", "test-project"
        ), patch(
            "tasks.data_import.data_import_utils.DATASET_BATCH_TOPIC", "dataset-batch"
        ), patch.dict(
            os.environ, {"COMMIT_BATCH_SIZE": "1"}, clear=False
        ):
            result = import_jbda_handler({"dry_run": False})

        # Summary checks (unchanged intent)
        self.assertEqual(
            {
                "message": "JBDA import executed successfully.",
                "created_gtfs": 1,
                "updated_gtfs": 0,
                "created_rt": 2,
                "linked_refs": 2,  # per RT link (tu + vp)
                "total_processed_items": 1,
                "params": {"dry_run": False},
            },
            result,
        )

        # DB checks for GTFS feed
        sched = (
            db_session.query(Gtfsfeed)
            .filter(Gtfsfeed.stable_id == "jbda-org1-feed1")
            .first()
        )
        self.assertIsNotNone(sched)
        self.assertEqual(sched.feed_name, "Feed One")
        # producer_url now points to the verified JBDA URL (HEAD-checked)
        self.assertEqual(sched.producer_url, url_current)

        # Related links (only next_1 exists) – also uses JBDA URL
        links: List[Feedrelatedlink] = list(sched.feedrelatedlinks)
        codes = {link.code for link in links}
        self.assertIn("jbda-next_1", codes)
        next1 = next(link for link in links if link.code == "jbda-next_1")
        self.assertEqual(next1.url, url_next1)

        # RT feeds + entity types + back-links
        tu = (
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == "jbda-org1-feed1-tu")
            .first()
        )
        vp = (
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == "jbda-org1-feed1-vp")
            .first()
        )
        self.assertIsNotNone(tu)
        self.assertIsNotNone(vp)
        self.assertEqual(len(tu.entitytypes), 1)
        self.assertEqual(len(vp.entitytypes), 1)
        self.assertEqual(tu.entitytypes[0].name, "tu")
        self.assertEqual(vp.entitytypes[0].name, "vp")
        self.assertEqual([f.id for f in tu.gtfs_feeds], [sched.id])
        self.assertEqual([f.id for f in vp.gtfs_feeds], [sched.id])
        self.assertEqual(tu.producer_url, "https://rt.example/one/tu.pb")
        self.assertEqual(vp.producer_url, "https://rt.example/one/vp.pb")

        # Pub/Sub was called exactly once (only 1 new GTFS feed)
        self.assertEqual(len(fake_pub.published), 1)
        topic_path, data_bytes = fake_pub.published[0]
        self.assertEqual(topic_path, "projects/test-project/topics/dataset-batch")

        payload = json.loads(data_bytes.decode("utf-8"))
        self.assertEqual(payload["feed_stable_id"], "jbda-org1-feed1")
        self.assertEqual(payload["producer_url"], url_current)
        self.assertIsNone(payload["dataset_id"])
        self.assertIsNone(payload["dataset_hash"])

    @with_db_session(db_url=default_db_url)
    def test_import_http_failure_graceful(self, db_session: Session):
        with patch(
            "tasks.data_import.jbda.import_jbda_feeds.requests.Session",
            return_value=_FakeSessionError(),
        ), patch("tasks.data_import.jbda.import_jbda_feeds.REQUEST_TIMEOUT_S", 0.01):
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
