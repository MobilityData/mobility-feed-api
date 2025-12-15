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
from tasks.data_import.data_import_utils import get_or_create_feed
from tasks.data_import.transportdatagouv.update_tdg_redirects import (
    update_tdg_redirects_handler,
    _update_feed_redirect,
)
from test_shared.test_utils.database_utils import default_db_url

TEST_STABLE_IDS = {
    "mdb-foo",
    "tdg-bar",
    "mdb-missing",
    "tdg-missing",
}


@with_db_session(db_url=default_db_url)
def _cleanup_tdg_redirect_test_data(db_session: Session):
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


class TestUpdateTDGRedirectsHelpers(unittest.TestCase):
    def tearDown(self):
        _cleanup_tdg_redirect_test_data()

    @with_db_session(db_url=default_db_url)
    def test_update_feed_redirect_creates_redirect(self, db_session: Session):
        """
        If both MDB and TDG feeds exist and no redirect is present,
        _update_feed_redirect should create one and return proper counters.
        """
        mdb_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "mdb-foo", "gtfs")
        tdg_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "tdg-bar", "gtfs")
        db_session.flush()

        counters = _update_feed_redirect(
            db_session=db_session,
            mdb_stable_id="mdb-foo",
            tdg_stable_id="tdg-bar",
        )

        self.assertEqual(counters["redirects_created"], 1)
        self.assertEqual(counters["redirects_existing"], 0)
        self.assertEqual(counters["missing_mdb_feeds"], 0)
        self.assertEqual(counters["missing_tdg_feeds"], 0)
        db_session.commit()

        redirect: Optional[Redirectingid] = (
            db_session.query(Redirectingid)
            .filter(
                Redirectingid.source_id == mdb_feed.id,
                Redirectingid.target_id == tdg_feed.id,
            )
            .one_or_none()
        )
        self.assertIsNotNone(redirect)
        self.assertEqual(redirect.redirect_comment, "Redirecting post TDG import")

    @with_db_session(db_url=default_db_url)
    def test_update_feed_redirect_missing_mdb(self, db_session: Session):
        """
        If MDB feed is missing, it should be counted and no redirect created.
        """
        tdg_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "tdg-bar", "gtfs")
        db_session.flush()

        counters = _update_feed_redirect(
            db_session=db_session,
            mdb_stable_id="mdb-missing",
            tdg_stable_id="tdg-bar",
        )

        self.assertEqual(counters["redirects_created"], 0)
        self.assertEqual(counters["redirects_existing"], 0)
        self.assertEqual(counters["missing_mdb_feeds"], 1)
        self.assertEqual(counters["missing_tdg_feeds"], 0)

        redirects = db_session.query(Redirectingid).all()
        self.assertEqual(len(redirects), 0)

    @with_db_session(db_url=default_db_url)
    def test_update_feed_redirect_missing_tdg(self, db_session: Session):
        """
        If TDG feed is missing, it should be counted and no redirect created.
        """
        mdb_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "mdb-foo", "gtfs")
        db_session.flush()

        counters = _update_feed_redirect(
            db_session=db_session,
            mdb_stable_id="mdb-foo",
            tdg_stable_id="tdg-missing",
        )

        self.assertEqual(counters["redirects_created"], 0)
        self.assertEqual(counters["redirects_existing"], 0)
        self.assertEqual(counters["missing_mdb_feeds"], 0)
        self.assertEqual(counters["missing_tdg_feeds"], 1)

        redirects = db_session.query(Redirectingid).all()
        self.assertEqual(len(redirects), 0)

    @with_db_session(db_url=default_db_url)
    def test_update_feed_redirect_existing_redirect(self, db_session: Session):
        """
        If redirect already exists, it should be counted as existing
        and no new row created.
        """
        mdb_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "mdb-foo", "gtfs")
        tdg_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "tdg-bar", "gtfs")
        db_session.flush()

        existing = Redirectingid(
            source_id=mdb_feed.id,
            target_id=tdg_feed.id,
            redirect_comment="Existing redirect",
        )
        db_session.add(existing)
        db_session.flush()

        counters = _update_feed_redirect(
            db_session=db_session,
            mdb_stable_id="mdb-foo",
            tdg_stable_id="tdg-bar",
        )

        self.assertEqual(counters["redirects_created"], 0)
        self.assertEqual(counters["redirects_existing"], 1)
        self.assertEqual(counters["missing_mdb_feeds"], 0)
        self.assertEqual(counters["missing_tdg_feeds"], 0)

        redirects = db_session.query(Redirectingid).all()
        self.assertEqual(len(redirects), 1)


class TestUpdateTDGRedirectsHandler(unittest.TestCase):
    def tearDown(self):
        _cleanup_tdg_redirect_test_data()

    @with_db_session(db_url=default_db_url)
    def test_handler_creates_redirects_from_csv(self, db_session: Session):
        """
        Happy path:
          - CSV has one row with MDB ID + raw TDG ID
          - MDB and corresponding TDG feeds exist
          - handler creates one redirect and commits it
        """
        mdb_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "mdb-foo", "gtfs")
        tdg_feed, _ = get_or_create_feed(db_session, Gtfsfeed, "tdg-bar", "gtfs")
        db_session.commit()

        df = pd.DataFrame(
            [
                {
                    "MDB ID": "mdb-foo",
                    "TDG ID": "bar",  # maps to "tdg-bar"
                }
            ]
        )

        with patch(
            "tasks.data_import.transportdatagouv.update_tdg_redirects.pd.read_csv",
            return_value=df,
        ), patch.dict(
            os.environ,
            {"COMMIT_BATCH_SIZE": "1"},
            clear=False,
        ):
            result = update_tdg_redirects_handler({"dry_run": False})

        self.assertEqual(
            result,
            {
                "message": "TDG redirects update executed successfully.",
                "rows_processed": 1,
                "redirects_created": 1,
                "redirects_existing": 0,
                "missing_mdb_feeds": 0,
                "missing_tdg_feeds": 0,
                "params": {"dry_run": False},
            },
        )

        redirect: Optional[Redirectingid] = (
            db_session.query(Redirectingid)
            .filter(
                Redirectingid.source_id == mdb_feed.id,
                Redirectingid.target_id == tdg_feed.id,
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
            "tasks.data_import.transportdatagouv.update_tdg_redirects.pd.read_csv",
            side_effect=RuntimeError("boom"),
        ):
            result = update_tdg_redirects_handler({"dry_run": True})

        self.assertEqual(result["message"], "Failed to load TDG redirect CSV.")
        self.assertIn("error", result)
        self.assertEqual(result["rows_processed"], 0)
        self.assertEqual(result["redirects_created"], 0)
        self.assertEqual(result["redirects_existing"], 0)
        self.assertEqual(result["missing_mdb_feeds"], 0)
        self.assertEqual(result["missing_tdg_feeds"], 0)


if __name__ == "__main__":
    unittest.main()
