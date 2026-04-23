import os
import unittest
from typing import Optional
from unittest.mock import patch

import pandas as pd
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsfeed,
    Redirectingid,
)
from tasks.data_import.cal_itp.update_cal_itp_redirects import update_cal_itp_redirects_handler
from tasks.data_import.data_import_utils import get_or_create_feed
from tasks.data_import.cal_itp.update_cal_itp_redirects import (
    update_cal_itp_redirects_handler,
    _update_feed_redirect,
)
from test_shared.test_utils.database_utils import default_db_url

# Realistic Cal-ITP stable ID: cal_itp-{service_source_record_id}-{type_code}
# The CSV "Cal-ITP ID" column holds only "{service_source_record_id}-{type_code}";
# the handler prepends "cal_itp-" to form the full stable_id.
TEST_CAL_ITP_SERVICE_ID = "recTEST0000000001"
TEST_CAL_ITP_STABLE_ID = f"cal_itp-{TEST_CAL_ITP_SERVICE_ID}-s"

TEST_STABLE_IDS = {
    "mdb-foo",
    "cal_itp-bar",
    TEST_CAL_ITP_STABLE_ID,
    "mdb-missing",
    "cal_itp-missing",
}


@with_db_session(db_url=default_db_url)
def _cleanup_cal_itp_redirect_test_data(db_session: Session):
    """
    Remove only the feeds / redirects created by this test suite,
    identified by their stable_ids.
    """
    # Find feeds created for this test suite
    feeds = db_session.query(Feed).filter(Feed.stable_id.in_(TEST_STABLE_IDS)).all()

    if not feeds:
        return

    feed_ids = [f.id for f in feeds]

    # Delete Redirectingid rows involving these feeds
    (
        db_session.query(Redirectingid)
        .filter(
            (Redirectingid.source_id.in_(feed_ids))
            | (Redirectingid.target_id.in_(feed_ids))
        )
        .delete(synchronize_session=False)
    )

    # Delete the feeds themselves (should cascade to Gtfsfeed, etc., if configured)
    for feed in feeds:
        db_session.delete(feed)


class TestUpdateCalItpRedirectsHelpers(unittest.TestCase):
    def tearDown(self):
        _cleanup_cal_itp_redirect_test_data()

    @with_db_session(db_url=default_db_url)
    def test_update_feed_redirect_creates_redirect(self, db_session: Session):
        """
        If both MDB and Cal-ITP feeds exist and no redirect is present,
        _update_feed_redirect should create one and return proper counters.
        """
        mdb_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "mdb-foo", "gtfs")
        cal_itp_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "cal-itp-bar", "gtfs")
        db_session.flush()

        counters = _update_feed_redirect(
            db_session=db_session,
            mdb_stable_id="mdb-foo",
            cal_itp_stable_id="cal-itp-bar",
        )

        self.assertEqual(counters["redirects_created"], 1)
        self.assertEqual(counters["redirects_existing"], 0)
        self.assertEqual(counters["missing_mdb_feeds"], 0)
        self.assertEqual(counters["missing_cal_itp_feeds"], 0)
        db_session.commit()

        redirect: Optional[Redirectingid] = (
            db_session.query(Redirectingid)
            .filter(
                Redirectingid.source_id == mdb_feed.id,
                Redirectingid.target_id == cal_itp_feed.id,
            )
            .one_or_none()
        )
        self.assertIsNotNone(redirect)
        self.assertEqual(redirect.redirect_comment, "Redirecting post Cal-ITP import")

    @with_db_session(db_url=default_db_url)
    def test_update_feed_redirect_missing_mdb(self, db_session: Session):
        """
        If MDB feed is missing, it should be counted and no redirect created.
        """
        cal_itp_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "cal-itp-bar", "gtfs")
        db_session.flush()

        counters = _update_feed_redirect(
            db_session=db_session,
            mdb_stable_id="mdb-missing",
            cal_itp_stable_id="cal-itp-bar",
        )

        self.assertEqual(counters["redirects_created"], 0)
        self.assertEqual(counters["redirects_existing"], 0)
        self.assertEqual(counters["missing_mdb_feeds"], 1)
        self.assertEqual(counters["missing_cal_itp_feeds"], 0)

        redirects = db_session.query(Redirectingid).all()
        self.assertEqual(len(redirects), 0)

    @with_db_session(db_url=default_db_url)
    def test_update_feed_redirect_missing_cal_itp(self, db_session: Session):
        """
        If Cal-ITP feed is missing, it should be counted and no redirect created.
        """
        mdb_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "mdb-foo", "gtfs")
        db_session.flush()

        counters = _update_feed_redirect(
            db_session=db_session,
            mdb_stable_id="mdb-foo",
            cal_itp_stable_id="cal-itp-missing",
        )

        self.assertEqual(counters["redirects_created"], 0)
        self.assertEqual(counters["redirects_existing"], 0)
        self.assertEqual(counters["missing_mdb_feeds"], 0)
        self.assertEqual(counters["missing_cal_itp_feeds"], 1)

        redirects = db_session.query(Redirectingid).all()
        self.assertEqual(len(redirects), 0)

    @with_db_session(db_url=default_db_url)
    def test_update_feed_redirect_existing_redirect(self, db_session: Session):
        """
        If redirect already exists, it should be counted as existing
        and no new row created.
        """
        mdb_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "mdb-foo", "gtfs")
        cal_itp_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "cal-itp-bar", "gtfs")
        db_session.flush()

        existing = Redirectingid(
            source_id=mdb_feed.id,
            target_id=cal_itp_feed.id,
            redirect_comment="Existing redirect",
        )
        db_session.add(existing)
        db_session.flush()

        counters = _update_feed_redirect(
            db_session=db_session,
            mdb_stable_id="mdb-foo",
            cal_itp_stable_id="cal-itp-bar",
        )

        self.assertEqual(counters["redirects_created"], 0)
        self.assertEqual(counters["redirects_existing"], 1)
        self.assertEqual(counters["missing_mdb_feeds"], 0)
        self.assertEqual(counters["missing_cal_itp_feeds"], 0)

        redirects = db_session.query(Redirectingid).all()
        self.assertEqual(len(redirects), 1)


class TestUpdateCalItpRedirectsHandler(unittest.TestCase):
    def tearDown(self):
        _cleanup_cal_itp_redirect_test_data()

    @with_db_session(db_url=default_db_url)
    def test_handler_creates_redirects_from_csv(self, db_session: Session):
        """
        Happy path:
          - CSV has one row with MDB ID + raw Cal-ITP ID
          - MDB and corresponding Cal-ITP feeds exist
          - handler creates one redirect and commits it
        """
        mdb_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "mdb-foo", "gtfs")
        cal_itp_feed, _ = get_or_create_feed(db_session, Gtfsfeed, TEST_CAL_ITP_STABLE_ID, "gtfs")
        db_session.commit()

        df = pd.DataFrame(
            [
                {
                    "MDB ID": "mdb-foo",
                    # CSV holds only the "{service_id}-{type_code}" part; the handler prepends "cal_itp-"
                    "Cal-ITP ID": f"{TEST_CAL_ITP_SERVICE_ID}-s",
                }
            ]
        )

        with patch(
            "tasks.data_import.cal_itp.update_cal_itp_redirects.pd.read_csv",
            return_value=df,
        ), patch.dict(
            os.environ,
            {"COMMIT_BATCH_SIZE": "1"},
            clear=False,
        ):
            result = update_cal_itp_redirects_handler({"dry_run": False})

        self.assertEqual(
            result,
            {
                "message": "Cal-ITP redirects update executed successfully.",
                "rows_processed": 1,
                "redirects_created": 1,
                "redirects_existing": 0,
                "missing_mdb_feeds": 0,
                "missing_cal_itp_feeds": 0,
                "params": {"dry_run": False},
            },
        )

        redirect: Optional[Redirectingid] = (
            db_session.query(Redirectingid)
            .filter(
                Redirectingid.source_id == mdb_feed.id,
                Redirectingid.target_id == cal_itp_feed.id,
            )
            .one_or_none()
        )
        self.assertIsNotNone(redirect)

    def test_handler_csv_load_failure(self):
        """
        If pd.read_csv throws, handler should return an error summary
        and not raise.
        """
        with patch(
            "tasks.data_import.cal_itp.update_cal_itp_redirects.pd.read_csv",
            side_effect=RuntimeError("boom"),
        ):
            result = update_cal_itp_redirects_handler({"dry_run": True})

        self.assertEqual(result["message"], "Failed to load Cal-ITP redirect CSV.")
        self.assertIn("error", result)
        self.assertEqual(result["rows_processed"], 0)
        self.assertEqual(result["redirects_created"], 0)
        self.assertEqual(result["redirects_existing"], 0)
        self.assertEqual(result["missing_mdb_feeds"], 0)
        self.assertEqual(result["missing_cal_itp_feeds"], 0)


if __name__ == "__main__":
    unittest.main()
