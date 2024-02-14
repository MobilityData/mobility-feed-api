import contextlib
from datetime import datetime, timedelta
from typing import Final

from geoalchemy2 import WKTElement

from database.database import Database, generate_unique_id
from database_gen.sqlacodegen_models import Gtfsfeed, Gtfsrealtimefeed, Gtfsdataset, Externalid

TEST_GTFS_FEED_STABLE_IDS = ["mdb-1", "mdb-10", "mdb-20", "mdb-30"]
TEST_DATASET_STABLE_IDS = ["mdb-2", "mdb-3", "mdb-11", "mdb-12"]
TEST_GTFS_RT_FEED_STABLE_ID = "mdb-1561"
TEST_EXTERNAL_IDS = ["external_id_1", "external_id_2", "external_id_3", "external_id_4"]

date_string: Final[str] = "2024-01-31 00:00:00"
date_format: Final[str] = "%Y-%m-%d %H:%M:%S"
one_day: Final[timedelta] = timedelta(days=1)
datasets_download_first_date: Final[datetime] = datetime.strptime(date_string, date_format)


@contextlib.contextmanager
def populate_database(db: Database):
    gtfs_feed_ids = [generate_unique_id() for _ in range(len(TEST_GTFS_FEED_STABLE_IDS))]
    dataset_ids = [generate_unique_id() for _ in range(len(TEST_DATASET_STABLE_IDS))]
    gtfs_rt_feed_id = generate_unique_id()
    for stable_id, gtfs_feed_id in zip(TEST_GTFS_FEED_STABLE_IDS, gtfs_feed_ids):
        db.merge(Gtfsfeed(id=gtfs_feed_id, stable_id=stable_id, data_type="gtfs", status="active"), auto_commit=True)
    db.merge(
        Gtfsrealtimefeed(
            id=gtfs_rt_feed_id, stable_id=TEST_GTFS_RT_FEED_STABLE_ID, data_type="gtfs_rt", status="active"
        ),
        auto_commit=True,
    )
    min_lat = 37.615264
    max_lat = 38.2321
    min_lon = -84.8984452721203
    max_lon = -84.4789953029549
    polygon = (
        f"POLYGON(({min_lon} {min_lat}, {min_lon} {max_lat}, {max_lon} {max_lat}, {max_lon} {min_lat}, "
        f"{min_lon} {min_lat}))"
    )

    for idx, dataset_id in enumerate(dataset_ids):
        db.merge(
            Gtfsdataset(
                id=dataset_id,
                stable_id=TEST_DATASET_STABLE_IDS[idx],
                feed_id=gtfs_feed_ids[idx // 2],
                latest=idx % 2 == 1,
                bounding_box=WKTElement(polygon, srid=4326),
                downloaded_at=(datasets_download_first_date + idx * one_day),
            ),
            auto_commit=True,
        )
    for idx, external_id in enumerate(TEST_EXTERNAL_IDS):
        db.merge(
            Externalid(
                feed_id=gtfs_feed_ids[idx // 2],
                associated_id=external_id,
                source="source" + str(idx + 1),
            )
        )
    db.session.execute(
        f"INSERT INTO redirectingid (source_id, target_id) VALUES ('{gtfs_feed_ids[0]}', '{gtfs_feed_ids[1]}')"
    )
    db.session.execute(
        f"INSERT INTO redirectingid (source_id, target_id) VALUES ('{gtfs_feed_ids[1]}', '{gtfs_feed_ids[2]}')"
    )
    db.session.execute(
        f"INSERT INTO redirectingid (source_id, target_id) VALUES ('{gtfs_feed_ids[1]}', '{gtfs_feed_ids[3]}')"
    )
    db.commit()
    db.flush()
    yield db
    for dataset_id in dataset_ids:
        db.session.execute(f"DELETE FROM gtfsdataset where id ='{dataset_id}'")
    for external_id in TEST_EXTERNAL_IDS:
        db.session.execute(f"DELETE FROM externalid where associated_id = '{external_id}'")
    for gtfs_feed_id in gtfs_feed_ids:
        db.session.execute(
            f"DELETE from redirectingid where " f"source_id = '{gtfs_feed_id}' OR target_id = '{gtfs_feed_id}'"
        )
        db.session.execute(f"DELETE FROM gtfsfeed where id = '{gtfs_feed_id}'")

    db.session.execute(f"DELETE FROM gtfsrealtimefeed where id = '{gtfs_rt_feed_id}'")
    for feed_id in [*gtfs_feed_ids, gtfs_rt_feed_id]:
        db.session.execute(f"DELETE FROM feed where id = '{feed_id}'")
    db.commit()
