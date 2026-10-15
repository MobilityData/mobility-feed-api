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
"""Integration tests for the sitemap queries against the real test database.

Each test class seeds its own rows under a dedicated id prefix and removes them
afterwards, so it neither depends on nor disturbs the shared conftest fixtures.
"""

import unittest
from datetime import date, datetime, timezone

from sqlalchemy import null, or_
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gbfsfeed,
    Gbfsversion,
    Gtfsdataset,
    Gtfsfeed,
    Gtfsrealtimefeed,
    t_feedreference,
)
from tasks.sitemap.generate_sitemap import (
    LASTMOD_FLOOR,
    collect_entries,
    fetch_gbfs_entries,
    fetch_gtfs_entries,
    fetch_gtfs_rt_entries,
)
from test_shared.test_utils.database_utils import default_db_url

PREFIX = "sitemap_test_"
AFTER_FLOOR = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
BEFORE_FLOOR = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)


def _feed_kwargs(suffix, **overrides):
    kwargs = {
        "id": f"{PREFIX}{suffix}",
        "stable_id": f"{PREFIX}{suffix}",
        "status": "active",
        "operational_status": "published",
        "created_at": BEFORE_FLOOR,
    }
    kwargs.update(overrides)
    return kwargs


@with_db_session(db_url=default_db_url)
def seed(db_session: Session = None):
    """Insert the sitemap fixtures. Safe to call after `unseed`."""
    # --- GTFS ---------------------------------------------------------------
    gtfs_recent = Gtfsfeed(**_feed_kwargs("gtfs_recent", data_type="gtfs"))
    gtfs_old = Gtfsfeed(**_feed_kwargs("gtfs_old", data_type="gtfs"))
    gtfs_no_dataset = Gtfsfeed(**_feed_kwargs("gtfs_no_dataset", data_type="gtfs"))
    gtfs_null_status = Gtfsfeed(
        # `status` has a server_default, so a plain `status=None` is treated by
        # the ORM as "unset" and the default fires instead; `null()` forces an
        # actual NULL to be inserted.
        **_feed_kwargs("gtfs_null_status", data_type="gtfs", status=null())
    )
    gtfs_deprecated = Gtfsfeed(
        **_feed_kwargs("gtfs_deprecated", data_type="gtfs", status="deprecated")
    )
    gtfs_wip = Gtfsfeed(
        **_feed_kwargs("gtfs_wip", data_type="gtfs", operational_status="wip")
    )
    db_session.add_all(
        [
            gtfs_recent,
            gtfs_old,
            gtfs_no_dataset,
            gtfs_null_status,
            gtfs_deprecated,
            gtfs_wip,
        ]
    )
    db_session.flush()

    # gtfs_recent has two datasets; the newest one must win.
    db_session.add_all(
        [
            Gtfsdataset(
                id=f"{PREFIX}ds_older",
                feed_id=gtfs_recent.id,
                stable_id=f"{PREFIX}ds_older",
                downloaded_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            ),
            Gtfsdataset(
                id=f"{PREFIX}ds_newest",
                feed_id=gtfs_recent.id,
                stable_id=f"{PREFIX}ds_newest",
                downloaded_at=AFTER_FLOOR,
            ),
            # Predates the floor, so the floor must win for this feed.
            Gtfsdataset(
                id=f"{PREFIX}ds_old",
                feed_id=gtfs_old.id,
                stable_id=f"{PREFIX}ds_old",
                downloaded_at=BEFORE_FLOOR,
            ),
        ]
    )

    # --- GTFS-RT ------------------------------------------------------------
    # Inherits its lastmod from the related scheduled feed's newest dataset.
    rt_with_parent = Gtfsrealtimefeed(
        **_feed_kwargs("rt_with_parent", data_type="gtfs_rt")
    )
    rt_with_parent.gtfs_feeds = [gtfs_recent]
    # No parent and a created_at before the floor: falls back to the floor.
    rt_orphan = Gtfsrealtimefeed(**_feed_kwargs("rt_orphan", data_type="gtfs_rt"))
    # No parent but created after the floor: its own created_at wins.
    rt_recent = Gtfsrealtimefeed(
        **_feed_kwargs("rt_recent", data_type="gtfs_rt", created_at=AFTER_FLOOR)
    )
    db_session.add_all([rt_with_parent, rt_orphan, rt_recent])

    # --- GBFS ---------------------------------------------------------------
    gbfs_versioned = Gbfsfeed(**_feed_kwargs("gbfs_versioned", data_type="gbfs"))
    gbfs_no_version = Gbfsfeed(**_feed_kwargs("gbfs_no_version", data_type="gbfs"))
    db_session.add_all([gbfs_versioned, gbfs_no_version])
    db_session.flush()
    db_session.add_all(
        [
            Gbfsversion(
                id=f"{PREFIX}v23",
                feed_id=gbfs_versioned.id,
                version="2.3",
                url="http://example.org/2.3",
                created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
            Gbfsversion(
                id=f"{PREFIX}v30",
                feed_id=gbfs_versioned.id,
                version="3.0",
                url="http://example.org/3.0",
                created_at=AFTER_FLOOR,
            ),
        ]
    )
    db_session.commit()


@with_db_session(db_url=default_db_url)
def unseed(db_session: Session = None):
    """Remove every row this module created.

    Core deletes in FK order: the subclass tables (`gtfsfeed`, `gbfsfeed`, ...)
    reference `feed.id` without ON DELETE CASCADE, so the base rows can only go
    once their subclass rows and every dependent row are gone.
    """
    feed_ids = [
        row[0] for row in db_session.query(Feed.id).filter(Feed.id.like(f"{PREFIX}%"))
    ]
    if not feed_ids:
        return
    db_session.execute(
        Gbfsversion.__table__.delete().where(Gbfsversion.feed_id.in_(feed_ids))
    )
    db_session.execute(
        Gtfsdataset.__table__.delete().where(Gtfsdataset.feed_id.in_(feed_ids))
    )
    db_session.execute(
        t_feedreference.delete().where(
            or_(
                t_feedreference.c.gtfs_rt_feed_id.in_(feed_ids),
                t_feedreference.c.gtfs_feed_id.in_(feed_ids),
            )
        )
    )
    for table in (
        Gtfsfeed.__table__,
        Gtfsrealtimefeed.__table__,
        Gbfsfeed.__table__,
        Feed.__table__,
    ):
        db_session.execute(table.delete().where(table.c.id.in_(feed_ids)))
    db_session.commit()


def setUpModule():
    unseed()
    seed()


def tearDownModule():
    unseed()


def as_map(entries):
    return {entry.stable_id: entry for entry in entries}


class TestFetchGtfsEntries(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session: Session = None):
        self.entries = as_map(fetch_gtfs_entries(db_session, LASTMOD_FLOOR))

    def test_lastmod_is_the_newest_dataset_download(self):
        self.assertEqual(
            self.entries[f"{PREFIX}gtfs_recent"].lastmod, AFTER_FLOOR.date()
        )

    def test_dataset_older_than_the_floor_falls_back_to_the_floor(self):
        self.assertEqual(self.entries[f"{PREFIX}gtfs_old"].lastmod, LASTMOD_FLOOR)

    def test_feed_without_any_dataset_is_still_included_at_the_floor(self):
        self.assertEqual(
            self.entries[f"{PREFIX}gtfs_no_dataset"].lastmod, LASTMOD_FLOOR
        )

    def test_null_status_feed_is_excluded(self):
        self.assertNotIn(f"{PREFIX}gtfs_null_status", self.entries)

    def test_deprecated_feed_is_excluded(self):
        self.assertNotIn(f"{PREFIX}gtfs_deprecated", self.entries)

    def test_non_published_feed_is_excluded(self):
        self.assertNotIn(f"{PREFIX}gtfs_wip", self.entries)

    def test_every_entry_is_tagged_gtfs(self):
        seeded = [k for k in self.entries if k.startswith(PREFIX)]
        self.assertTrue(seeded)
        for stable_id in seeded:
            self.assertEqual(self.entries[stable_id].data_type, "gtfs")

    def test_no_realtime_or_gbfs_feed_leaks_in(self):
        self.assertNotIn(f"{PREFIX}rt_with_parent", self.entries)
        self.assertNotIn(f"{PREFIX}gbfs_versioned", self.entries)


class TestFetchGtfsRtEntries(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session: Session = None):
        self.entries_list = fetch_gtfs_rt_entries(db_session, LASTMOD_FLOOR)
        self.entries = as_map(self.entries_list)

    def test_lastmod_comes_from_the_related_scheduled_feed(self):
        self.assertEqual(
            self.entries[f"{PREFIX}rt_with_parent"].lastmod, AFTER_FLOOR.date()
        )

    def test_feed_without_a_scheduled_reference_falls_back_to_the_floor(self):
        self.assertEqual(self.entries[f"{PREFIX}rt_orphan"].lastmod, LASTMOD_FLOOR)

    def test_own_created_at_wins_when_it_is_newer_than_the_floor(self):
        self.assertEqual(self.entries[f"{PREFIX}rt_recent"].lastmod, AFTER_FLOOR.date())

    def test_the_join_does_not_duplicate_a_feed_with_references(self):
        matches = [
            e for e in self.entries_list if e.stable_id == f"{PREFIX}rt_with_parent"
        ]
        self.assertEqual(len(matches), 1)

    def test_every_entry_is_tagged_gtfs_rt(self):
        for stable_id, entry in self.entries.items():
            if stable_id.startswith(PREFIX):
                self.assertEqual(entry.data_type, "gtfs_rt")


class TestFetchGbfsEntries(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session: Session = None):
        self.entries = as_map(fetch_gbfs_entries(db_session, LASTMOD_FLOOR))

    def test_lastmod_is_the_newest_gbfs_version_date(self):
        self.assertEqual(
            self.entries[f"{PREFIX}gbfs_versioned"].lastmod, AFTER_FLOOR.date()
        )

    def test_feed_without_any_version_falls_back_to_the_floor(self):
        self.assertEqual(
            self.entries[f"{PREFIX}gbfs_no_version"].lastmod, LASTMOD_FLOOR
        )

    def test_every_entry_is_tagged_gbfs(self):
        for stable_id, entry in self.entries.items():
            if stable_id.startswith(PREFIX):
                self.assertEqual(entry.data_type, "gbfs")


class TestCollectEntries(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def setUp(self, db_session: Session = None):
        self.entries = collect_entries(db_session)

    def test_entries_are_grouped_by_data_type_then_sorted_by_stable_id(self):
        order = {"gtfs": 0, "gtfs_rt": 1, "gbfs": 2}
        keys = [(order[e.data_type], e.stable_id) for e in self.entries]
        self.assertEqual(keys, sorted(keys))

    def test_stable_ids_are_unique(self):
        stable_ids = [e.stable_id for e in self.entries]
        self.assertEqual(len(stable_ids), len(set(stable_ids)))

    def test_no_entry_predates_the_floor(self):
        for entry in self.entries:
            self.assertGreaterEqual(entry.lastmod, LASTMOD_FLOOR)

    def test_lastmod_is_always_a_date(self):
        for entry in self.entries:
            self.assertIsInstance(entry.lastmod, date)

    def test_all_three_data_types_are_represented(self):
        self.assertEqual(
            {e.data_type for e in self.entries if e.stable_id.startswith(PREFIX)},
            {"gtfs", "gtfs_rt", "gbfs"},
        )


if __name__ == "__main__":
    unittest.main()
