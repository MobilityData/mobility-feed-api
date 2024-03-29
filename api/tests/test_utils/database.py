import contextlib
from datetime import datetime, timedelta
from typing import Final

from geoalchemy2 import WKTElement

from database.database import Database, generate_unique_id
from database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsrealtimefeed,
    Gtfsdataset,
    Externalid,
    Validationreport,
    Notice,
    Feature,
)

TEST_GTFS_FEED_STABLE_IDS = ["mdb-1", "mdb-10", "mdb-20", "mdb-30"]
TEST_DATASET_STABLE_IDS = ["mdb-2", "mdb-3", "mdb-11", "mdb-12"]
TEST_GTFS_RT_FEED_STABLE_ID = "mdb-1561"
TEST_EXTERNAL_IDS = ["external_id_1", "external_id_2", "external_id_3", "external_id_4"]
OLD_VALIDATION_VERSION = "1.0.0"
OLD_VALIDATION_TIME = datetime.utcnow() - timedelta(hours=1)
NEW_VALIDATION_VERSION = "2.0.0"
NEW_VALIDATION_TIME = datetime.utcnow()
VALIDATION_INFO_COUNT_PER_NOTICE = 5
VALIDATION_INFO_NOTICES = 10
VALIDATION_WARNING_COUNT_PER_NOTICE = 3
VALIDATION_WARNING_NOTICES = 4
VALIDATION_ERROR_COUNT_PER_NOTICE = 2
VALIDATION_ERROR_NOTICES = 7
FEATURE_IDS = [generate_unique_id() for _ in range(3)]

date_string: Final[str] = "2024-01-31 00:00:00"
date_format: Final[str] = "%Y-%m-%d %H:%M:%S"
one_day: Final[timedelta] = timedelta(days=1)
datasets_download_first_date: Final[datetime] = datetime.strptime(date_string, date_format)


@contextlib.contextmanager
def populate_database(db: Database):
    gtfs_feed_ids = [generate_unique_id() for _ in range(len(TEST_GTFS_FEED_STABLE_IDS))]
    dataset_ids = [generate_unique_id() for _ in range(len(TEST_DATASET_STABLE_IDS))]
    gtfs_rt_feed_id = generate_unique_id()

    try:
        for stable_id, gtfs_feed_id in zip(TEST_GTFS_FEED_STABLE_IDS, gtfs_feed_ids):
            db.merge(
                Gtfsfeed(id=gtfs_feed_id, stable_id=stable_id, data_type="gtfs", status="active"), auto_commit=True
            )
        for feature_id in FEATURE_IDS:
            db.merge(Feature(name=feature_id), auto_commit=True)
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
            # for each dataset, create two validation reports, one old and one new
            old_validation_report = Validationreport(
                id=generate_unique_id(),
                validator_version=OLD_VALIDATION_VERSION,
                validated_at=OLD_VALIDATION_TIME,
            )
            new_validation_report = Validationreport(
                id=generate_unique_id(),
                validator_version=NEW_VALIDATION_VERSION,
                validated_at=NEW_VALIDATION_TIME,
            )

            db.merge(
                Gtfsdataset(
                    id=dataset_id,
                    stable_id=TEST_DATASET_STABLE_IDS[idx],
                    feed_id=gtfs_feed_ids[idx // 2],
                    latest=idx % 2 == 1,
                    bounding_box=WKTElement(polygon, srid=4326),
                    validation_reports=[old_validation_report, new_validation_report],
                    # This makes downloaded_at predictable and unique for each dataset
                    downloaded_at=(datasets_download_first_date + idx * one_day),
                ),
                auto_commit=True,
            )

            # create multiple notices for each severity level
            for _ in range(VALIDATION_INFO_NOTICES):
                db.merge(
                    Notice(
                        dataset_id=dataset_id,
                        validation_report_id=new_validation_report.id,
                        notice_code=generate_unique_id(),
                        severity="INFO",
                        total_notices=VALIDATION_INFO_COUNT_PER_NOTICE,
                    ),
                )
            for _ in range(VALIDATION_WARNING_NOTICES):
                db.merge(
                    Notice(
                        dataset_id=dataset_id,
                        validation_report_id=new_validation_report.id,
                        notice_code=generate_unique_id(),
                        severity="WARNING",
                        total_notices=VALIDATION_WARNING_COUNT_PER_NOTICE,
                    ),
                )
            for _ in range(VALIDATION_ERROR_NOTICES):
                db.merge(
                    Notice(
                        dataset_id=dataset_id,
                        validation_report_id=new_validation_report.id,
                        notice_code=generate_unique_id(),
                        severity="ERROR",
                        total_notices=VALIDATION_ERROR_COUNT_PER_NOTICE,
                    ),
                )
            # for feature_id in FEATURE_IDS:
            #     db.session.execute(
            #         f"INSERT INTO featurevalidationreport (feature, dataset_id) " f"VALUES ('{feature_id}', '{validation_id}')"
            #     )

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
    except Exception as e:
        print(e)
    finally:
        # clean up the testing data regardless of the test result
        for dataset_id in dataset_ids:
            db.session.execute(f"DELETE FROM notice where dataset_id ='{dataset_id}'")
            db.session.execute(f"DELETE FROM validationreportgtfsdataset where dataset_id ='{dataset_id}'")
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
        db.session.execute(
            f"""DELETE FROM feature where name in ({', '.join(["'" + feature_id + "'"
                                                                                for feature_id
                                                                                in FEATURE_IDS])})"""
        )
        db.commit()
