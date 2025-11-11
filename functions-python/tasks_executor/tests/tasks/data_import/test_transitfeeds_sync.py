import os
import unittest
from unittest.mock import patch

import pandas as pd
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsrealtimefeed,
    Gtfsdataset,
)
from tasks.data_import.transitfeeds.sync_transitfeeds import (
    sync_transitfeeds_handler,
)
from test_shared.test_utils.database_utils import default_db_url


# ─────────────────────────────────────────────────────────────────────────────
# Helpers to fabricate CSV DataFrames
# ─────────────────────────────────────────────────────────────────────────────


def _df_gtfs_feeds() -> pd.DataFrame:
    # Minimal columns used by the loader
    return pd.DataFrame(
        [
            {
                "Mobility Database Feed ID": "mdb-123",
                "Feed Name": "Sample Feed",
                "External Feed ID": "tf-777",
                "Provider": "Provider A",
                "Producer URL": "https://example.com/a.zip",
                "Redirects": "",  # keep empty to avoid FK lookups
                "Country": "Canada",
                "Subdivision": "QC",
                "Municipality": "Laval",
            }
        ]
    )


def _df_gtfs_rt_feeds() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Mobility Database Feed ID": "mdb-rt-1",
                "Feed Name": "Sample RT Feed",
                "External Feed ID": "tf-rt-999",
                "Provider": "Provider A",
                "Producer URL": "https://rt.example.com/endpoint",
                "Redirects": "",
                "Country": "Canada",
                "Subdivision": "QC",
                "Municipality": "Laval",
                # Entity types separated by ' | ' to hit _safe_split
                "Entity Types": "tu | vp",
            }
        ]
    )


def _df_historical_datasets() -> pd.DataFrame:
    # Two datasets for mdb-123; the "Dataset ID" suffix encodes YYYYMMDD-...
    # Code sorts descending by 'Dataset ID', so 20250101 comes before 20241201.
    return pd.DataFrame(
        [
            {
                "Feed ID": "mdb-123",
                "Dataset ID": "provider/feed/20250101-releaseA",
                "Service Date Range Start": "20250101",
                "Service Date Range End": "20250331",
            },
            {
                "Feed ID": "mdb-123",
                "Dataset ID": "provider/feed/20241201-releaseB",
                "Service Date Range Start": "20241201",
                "Service Date Range End": "20250228",
            },
        ]
    )


def _read_csv_side_effect(path: str, *args, **kwargs) -> pd.DataFrame:
    fname = os.path.basename(path)
    if fname == "gtfs_feeds.csv":
        return _df_gtfs_feeds()
    if fname == "gtfs_rt_feeds.csv":
        return _df_gtfs_rt_feeds()
    if fname == "historical_datasets.csv":
        return _df_historical_datasets()
    raise AssertionError(f"Unexpected CSV read: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTransitFeedsSync(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def test_sync_creates_feeds_and_datasets(self, db_session: Session):
        # Arrange CSVs
        with patch(
            "tasks.data_import.transitfeeds.sync_transitfeeds.pd.read_csv",
            side_effect=_read_csv_side_effect,
        ):
            # Act
            result = sync_transitfeeds_handler({"dry_run": False})

        # Assert handler summary
        self.assertIn("message", result)
        self.assertIn("total_processed", result)
        self.assertIn("datasets_added", result)
        self.assertEqual(result["total_processed"], 2)  # 1 GTFS + 1 RT row
        self.assertEqual(result["datasets_added"], 2)

        # Verify GTFS feed was created
        gtfs: Gtfsfeed | None = (
            db_session.query(Gtfsfeed).filter(Gtfsfeed.stable_id == "mdb-123").first()
        )
        self.assertIsNotNone(gtfs)
        self.assertEqual(gtfs.status, "deprecated")
        # Externalids contains transitfeeds entry
        self.assertTrue(
            any(
                e.source == "transitfeeds" and e.associated_id == "tf-777"
                for e in (gtfs.externalids or [])
            )
        )
        # Location assigned once
        self.assertTrue(gtfs.locations)
        self.assertEqual(getattr(gtfs.locations[0], "subdivision_name", None), "QC")

        # Historical datasets created (2) & latest_dataset_id points to newest
        datasets = (
            db_session.query(Gtfsdataset).filter(Gtfsdataset.feed_id == gtfs.id).all()
        )
        self.assertEqual(len(datasets), 2)

        newest_stable = "mdb-123-20250101-releaseA"
        newest = next(ds for ds in datasets if ds.stable_id == newest_stable)
        self.assertEqual(gtfs.latest_dataset_id, newest.id)

        # Verify RT feed creation and entity types
        rt: Gtfsrealtimefeed | None = (
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == "mdb-rt-1")
            .first()
        )
        self.assertIsNotNone(rt)
        # entity_types relationship name is 'entity_types' in your code path
        et_names = [getattr(et, "name", None) for et in (rt.entitytypes or [])]
        self.assertCountEqual(et_names, ["tu", "vp"])

    @with_db_session(db_url=default_db_url)
    def test_sync_handles_missing_redirect_targets_and_empty_history(
        self, db_session: Session
    ):
        # Build CSVs where GTFS has a bogus redirect; historical is empty
        df_gtfs = _df_gtfs_feeds().copy()
        df_gtfs.loc[0, "Redirects"] = "nonexistent-id"
        df_rt = _df_gtfs_rt_feeds().copy()
        df_hist = pd.DataFrame(
            columns=[
                "Feed ID",
                "Dataset ID",
                "Service Date Range Start",
                "Service Date Range End",
            ]
        )

        def _side_effect(path: str, *args, **kwargs):
            fname = os.path.basename(path)
            if fname == "gtfs_feeds.csv":
                return df_gtfs
            if fname == "gtfs_rt_feeds.csv":
                return df_rt
            if fname == "historical_datasets.csv":
                return df_hist
            raise AssertionError(f"Unexpected CSV read: {path}")

        with patch(
            "tasks.data_import.transitfeeds.sync_transitfeeds.pd.read_csv",
            side_effect=_side_effect,
        ):
            out = sync_transitfeeds_handler({"dry_run": False})

        # We processed 2 feeds; datasets_added is 0
        self.assertEqual(out["total_processed"], 2)
        self.assertEqual(out["datasets_added"], 0)

        # GTFS feed exists even though redirect target was missing
        gtfs = (
            db_session.query(Gtfsfeed).filter(Gtfsfeed.stable_id == "mdb-123").first()
        )
        self.assertIsNotNone(gtfs)


if __name__ == "__main__":
    unittest.main()
