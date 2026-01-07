import datetime
import uuid
from sqlalchemy.orm import Session

from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsrealtimefeed,
    Gtfsdataset,
    Location,
    Osmlocationgroup,
    Feedlocationgrouppoint,
    Externalid,
    Entitytype,
    Feedosmlocationgroup,
    Feature,
    Validationreport,
    Officialstatushistory,
    Redirectingid,
    Gbfsendpoint,
    Gbfsversion,
    Gbfsfeed,
    Httpaccesslog,
    Gbfsvalidationreport,
    Gbfsnotice,
    Notice,
    Gtfsfeed,
    Geopolygon,
    FeedLicenseChange,
)

from sqlalchemy import text
from geoalchemy2 import WKTElement


def delete_and_assert(session: "Session", sql_queries: list[str], parent_instance):

    # Assert all queries return 1 before deletion
    for sql_query in sql_queries:
        count = session.execute(text(sql_query)).scalar()
        assert count == 1, f"Expected count 1 before delete for query: {sql_query}, got {count}"

    session.delete(parent_instance)
    session.commit()

    # Assert all queries return 0 after deletion
    for sql_query in sql_queries:
        count = session.execute(text(sql_query)).scalar()
        assert count == 0, f"Expected count 0 after delete for query: {sql_query}, got {count}"


def test_delete_feature_cascadeto_featurevalidationreport(test_database):

    with test_database.start_db_session() as session:
        feature = Feature(name="f1")
        validationreport = Validationreport(id="v1")

        session.add_all([feature, validationreport])
        feature.validations.append(validationreport)
        session.commit()

        delete_and_assert(
            session, ["SELECT COUNT(*) FROM feature", "SELECT COUNT(*) FROM featurevalidationreport"], feature
        )


def test_delete_feed_cascadeto_externalids(test_database):

    with test_database.start_db_session() as session:
        feed = Feed(id="f1")
        externalid = Externalid(feed_id="f1", associated_id="Some id 1")
        session.add_all([feed, externalid])
        session.commit()

        delete_and_assert(
            session,
            ["SELECT COUNT(*) FROM feed where id = 'f1'", "SELECT COUNT(*) FROM externalid where feed_id = 'f1'"],
            feed,
        )


def test_delete_feed_cascadeto_feedlocationgrouppoint(test_database):
    with test_database.start_db_session() as session:

        feed = Feed(id="f1")
        group = Osmlocationgroup(group_id="g1", group_name="G1")
        assoc = Feedlocationgrouppoint(feed_id="f1", group_id="g1", geometry=WKTElement("POINT (1.0 1.0)"))
        session.add_all([feed, group, assoc])
        session.commit()

        delete_and_assert(
            session,
            [
                "SELECT COUNT(*) FROM feed where id = 'f1'",
                "SELECT COUNT(*) FROM feedlocationgrouppoint where feed_id = 'f1'",
            ],
            feed,
        )


def test_delete_feed_cascadeto_feedosmlocationgroup(test_database):

    with test_database.start_db_session() as session:
        feed = Feed(id="f1")
        group = Osmlocationgroup(group_id="g1", group_name="G1")
        session.add_all([feed, group])
        feed.feedosmlocationgroups.append(Feedosmlocationgroup(feed_id="f1", group_id="g1", stops_count=1))
        session.commit()

        delete_and_assert(
            session,
            [
                "SELECT COUNT(*) FROM feed where id = 'f1'",
                "SELECT COUNT(*) FROM feedosmlocationgroup where feed_id = 'f1'",
            ],
            feed,
        )


def test_delete_feed_cascadeto_gtfsdataset(test_database):

    with test_database.start_db_session() as session:
        feed = Feed(id="f1")
        session.add(feed)
        session.flush()
        dataset = Gtfsdataset(id="d1", feed_id="f1")
        session.add(dataset)
        session.commit()

        delete_and_assert(
            session,
            ["SELECT COUNT(*) FROM feed where id = 'f1'", "SELECT COUNT(*) FROM gtfsdataset where feed_id = 'f1'"],
            feed,
        )


def test_delete_feed_cascadeto_locationfeed(test_database):
    with test_database.start_db_session() as session:
        feed = Feed(id="f1")
        location = Location(id="l1")
        session.add_all([feed, location])
        feed.locations.append(location)
        session.commit()

        delete_and_assert(
            session,
            ["SELECT COUNT(*) FROM feed where id = 'f1'", "SELECT COUNT(*) FROM locationfeed where feed_id = 'f1'"],
            feed,
        )


def test_cascade_delete_feed_officialstatushistory(test_database):

    with test_database.start_db_session() as session:
        feed = Feed(id="f1")
        officialstatushistory = Officialstatushistory(
            is_official=True, feed_id="f1", timestamp=datetime.datetime.now(), reviewer_email=""
        )
        session.add_all([feed, officialstatushistory])
        session.commit()

        delete_and_assert(
            session,
            [
                "SELECT COUNT(*) FROM feed where id = 'f1'",
                "SELECT COUNT(*) FROM officialstatushistory where feed_id = 'f1'",
            ],
            feed,
        )


def test_delete_feed_cascadeto_redirectingid(test_database):
    with test_database.start_db_session() as session:
        feed1 = Feed(id="f1")
        feed2 = Feed(id="f2")
        feed3 = Feed(id="f3")
        assoc1 = Redirectingid(source_id="f1", target_id="f2")
        assoc2 = Redirectingid(source_id="f2", target_id="f3")

        session.add_all([feed1, feed2, feed3, assoc1, assoc2])

        session.commit()

        assoc_count = session.execute(text("SELECT COUNT(*) FROM redirectingid")).scalar()
        assert assoc_count == 2

        session.delete(feed2)
        session.commit()
        assoc_count = session.execute(text("SELECT COUNT(*) FROM redirectingid")).scalar()
        assert assoc_count == 0


def test_delete_feed_cascadeto_feed_license_changes(test_database):

    with test_database.start_db_session() as session:
        feed = Feed(id="f1")
        feed_license_change = FeedLicenseChange(feed_id="f1")
        session.add_all([feed, feed_license_change])
        session.commit()

        delete_and_assert(
            session,
            [
                "SELECT COUNT(*) FROM feed where id = 'f1'",
                "SELECT COUNT(*) FROM feed_license_change where feed_id = 'f1'",
            ],
            feed,
        )


def test_delete_gbfsfeed_cascadeto_gbfsversion_cascadeto_gbfsendpoint_cascadeto_gbfsendpointhttpaccesslog(
    test_database,
):
    with test_database.start_db_session() as session:
        feed = Gbfsfeed(id="f1")
        version = Gbfsversion(id="v1", feed_id="f1", version="1.0", url="https://example.com/version")
        endpoint = Gbfsendpoint(id="e1", name="e1", gbfs_version_id="v1", url="https://example.com")
        accesslogid = uuid.uuid4()
        accesslog = Httpaccesslog(
            id=accesslogid, request_method="allo", request_url="https://example.com", status_code=200
        )
        endpoint.httpaccesslogs.append(accesslog)
        session.add_all([feed, version, endpoint, accesslog])
        session.commit()

        count = session.execute(text("SELECT COUNT(*) FROM gbfsendpoint WHERE id = 'e1'")).scalar()
        assert count == 1
        count = session.execute(text("SELECT COUNT(*) FROM gbfsversion WHERE id = 'v1'")).scalar()
        assert count == 1
        count = session.execute(text("SELECT COUNT(*) FROM httpaccesslog WHERE id = :id"), {"id": accesslogid}).scalar()
        assert count == 1
        count = session.execute(
            text("SELECT COUNT(*) FROM gbfsendpointhttpaccesslog WHERE gbfs_endpoint_id = 'e1'")
        ).scalar()
        assert count == 1

        session.delete(feed)
        session.commit()
        count = session.execute(text("SELECT COUNT(*) FROM gbfsendpoint WHERE id = 'e1'")).scalar()
        assert count == 0
        count = session.execute(text("SELECT COUNT(*) FROM gbfsversion WHERE id = 'v1'")).scalar()
        assert count == 0
        # Make sure the row in the association is deleted
        count = session.execute(
            text("SELECT COUNT(*) FROM gbfsendpointhttpaccesslog WHERE gbfs_endpoint_id = 'e1'")
        ).scalar()
        assert count == 0
        # But not the access log entry itself. The only way to delete this safely is if it's removed from
        # gbfsfeedhttpaccesslog and gbfsendpointhttpaccesslog, since both of these tables refer to Httpaccesslog
        count = session.execute(text("SELECT COUNT(*) FROM httpaccesslog WHERE id = :id"), {"id": accesslogid}).scalar()
        assert count == 1


def test_delete_gbfsfeed_cascadeto_gbfsfeedhttpaccesslog(test_database):
    with test_database.start_db_session() as session:
        feed = Gbfsfeed(id="f1")
        version = Gbfsversion(id="v1", feed_id="f1", version="1.0", url="https://example.com/version")
        endpoint = Gbfsendpoint(id="e1", name="e1", gbfs_version_id="v1", url="https://example.com")
        accesslogid = uuid.uuid4()
        accesslog = Httpaccesslog(
            id=accesslogid, request_method="allo", request_url="https://example.com", status_code=200
        )

        feed.httpaccesslogs.append(accesslog)
        endpoint.httpaccesslogs.append(accesslog)
        session.add_all([feed, version, endpoint, accesslog])

        session.commit()

        count = session.execute(text("SELECT COUNT(*) FROM gbfsfeedhttpaccesslog WHERE gbfs_feed_id = 'f1'")).scalar()
        assert count == 1

        session.delete(feed)
        session.commit()

        count = session.execute(text("SELECT COUNT(*) FROM gbfsfeedhttpaccesslog WHERE gbfs_feed_id = 'f1'")).scalar()
        assert count == 0


def test_delete_gbfsvalidationreport_cascadeto_gbfsnotice(test_database):
    with test_database.start_db_session() as session:
        feed = Gbfsfeed(id="f1")
        version = Gbfsversion(id="v1", feed_id="f1", version="1.0", url="https://example.com/version")
        validationreport = Gbfsvalidationreport(
            id="v1",
            gbfs_version_id="v1",
            report_summary_url="some url",
            total_errors_count=0,
            validator_version="2.3.0",
        )
        notice = Gbfsnotice(
            keyword="allo",
            message="some message",
            schema_path="some path",
            gbfs_file="some file",
            validation_report_id="v1",
            count=1,
        )
        session.add_all([feed, version, validationreport, notice])
        validationreport.gbfsnotices.append(notice)
        session.commit()

        delete_and_assert(
            session,
            [
                "SELECT COUNT(*) FROM gbfsvalidationreport where id = 'v1'",
                "SELECT COUNT(*) FROM gbfsnotice where validation_report_id = 'v1'",
            ],
            validationreport,
        )


def test_delete_gbfsfeed_cascadeto_gbfsversion_cascadeto_gbfsvalidationreport(test_database):
    with test_database.start_db_session() as session:
        feed = Gbfsfeed(id="f1")
        version = Gbfsversion(id="v1", feed_id="f1", version="1.0", url="https://example.com/version")
        validationreport = Gbfsvalidationreport(
            id="v1",
            gbfs_version_id="v1",
            report_summary_url="some url",
            total_errors_count=0,
            validator_version="2.3.0",
        )
        session.add_all([feed, version, validationreport])
        session.commit()

        delete_and_assert(
            session, ["SELECT COUNT(*) FROM gbfsversion", "SELECT COUNT(*) FROM gbfsvalidationreport"], feed
        )


def test_delete_gtfsdataset_cascadeto_location_gtfsdataset(test_database):
    with test_database.start_db_session() as session:
        dataset = Gtfsdataset(id="d1")
        location = Location(id="l1")
        session.add_all([dataset, location])
        session.flush()
        dataset.locations.append(location)
        session.commit()

        delete_and_assert(
            session,
            [
                "SELECT COUNT(*) FROM gtfsdataset",
                "SELECT COUNT(*) FROM location_gtfsdataset WHERE gtfsdataset_id = 'd1'",
            ],
            dataset,
        )


def test_delete_gtfsfeed_cascadeto_feedreference(test_database):
    with test_database.start_db_session() as session:
        gtfsfeed = Gtfsfeed(id="f1")
        gtfsrtfeed = Gtfsrealtimefeed(id="f2")
        session.add_all([gtfsfeed, gtfsrtfeed])
        gtfsfeed.gtfs_rt_feeds.append(gtfsrtfeed)
        session.commit()

        delete_and_assert(
            session, ["SELECT COUNT(*) FROM feed where id = 'f1'", "SELECT COUNT(*) FROM feedreference"], gtfsfeed
        )


def test_delete_gtfsrealtimefeed_cascadeto_feedreference(test_database):
    with test_database.start_db_session() as session:
        gtfsfeed = Gtfsfeed(id="f1")
        gtfsrtfeed = Gtfsrealtimefeed(id="f2")
        session.add_all([gtfsfeed, gtfsrtfeed])
        gtfsfeed.gtfs_rt_feeds.append(gtfsrtfeed)
        session.commit()

        delete_and_assert(
            session, ["SELECT COUNT(*) FROM feed where id = 'f2'", "SELECT COUNT(*) FROM feedreference"], gtfsrtfeed
        )


def test_delete_gtfsrealtimefeed_cascadeto_entitytypes(test_database):
    with test_database.start_db_session() as session:
        gtfsrtfeed = Gtfsrealtimefeed(id="f1")
        entitytype = Entitytype(name="type1")
        session.add_all([gtfsrtfeed, gtfsrtfeed])
        gtfsrtfeed.entitytypes.append(entitytype)
        session.commit()

        delete_and_assert(
            session,
            ["SELECT COUNT(*) FROM gtfsrealtimefeed where id = 'f1'", "SELECT COUNT(*) FROM entitytypefeed"],
            gtfsrtfeed,
        )


def test_delete_httpaccesslog_cascadeto_gbfsendpointhttpaccesslog(test_database):
    with (test_database.start_db_session() as session):
        feed = Gbfsfeed(id="f1")
        version = Gbfsversion(id="v1", feed_id="f1", version="1.0", url="https://example.com/version")
        endpoint = Gbfsendpoint(id="e1", name="e1", gbfs_version_id="v1", url="https://example.com")
        accesslogid = uuid.uuid4()
        accesslog = Httpaccesslog(
            id=accesslogid, request_method="allo", request_url="https://example.com", status_code=200
        )

        endpoint.httpaccesslogs.append(accesslog)
        session.add_all([feed, version, endpoint, accesslog])
        session.commit()

        delete_and_assert(
            session, ["SELECT COUNT(*) FROM httpaccesslog", "SELECT COUNT(*) FROM gbfsendpointhttpaccesslog"], accesslog
        )


def test_delete_httpaccesslog_cascadeto_gbfsfeedhttpaccesslog(test_database):
    with (test_database.start_db_session() as session):
        feed = Gbfsfeed(id="f1")
        version = Gbfsversion(id="v1", feed_id="f1", version="1.0", url="https://example.com/version")
        endpoint = Gbfsendpoint(id="e1", name="e1", gbfs_version_id="v1", url="https://example.com")
        accesslogid = uuid.uuid4()
        accesslog = Httpaccesslog(
            id=accesslogid, request_method="allo", request_url="https://example.com", status_code=200
        )

        feed.httpaccesslogs.append(accesslog)
        endpoint.httpaccesslogs.append(accesslog)
        session.add_all([feed, version, endpoint, accesslog])
        session.commit()

        delete_and_assert(
            session,
            ["SELECT COUNT(*) FROM gbfsfeed where id = 'f1'", "SELECT COUNT(*) FROM gbfsfeedhttpaccesslog"],
            feed,
        )


def test_delete_location_cascadeto_locationfeed(test_database):
    with (test_database.start_db_session() as session):
        feed = Gtfsfeed(id="f1")
        location = Location(id="l1")

        feed.locations.append(location)
        session.add_all([feed, location])
        session.commit()

        delete_and_assert(
            session, ["SELECT COUNT(*) FROM gtfsfeed where id = 'f1'", "SELECT COUNT(*) FROM locationfeed"], feed
        )


def test_delete_location_cascadeto_location_gtfsdataset(test_database):
    with (test_database.start_db_session() as session):

        location = Location(id="l1")
        dataset = Gtfsdataset(id="d1")
        session.add_all([dataset, location])
        dataset.locations.append(location)
        session.commit()

        delete_and_assert(
            session,
            ["SELECT COUNT(*) FROM gtfsdataset where id = 'd1'", "SELECT COUNT(*) FROM location_gtfsdataset"],
            dataset,
        )


def test_cascade_delete_osmlocationgroup_cascadeto_feedlocationgrouppoint(test_database):
    with test_database.start_db_session() as session:
        feed = Gtfsfeed(id="f1")
        group = Osmlocationgroup(group_id="g1", group_name="G1")
        assoc = Feedlocationgrouppoint(feed_id="f1", group_id="g1", geometry=WKTElement("POINT (1.0 1.0)"))
        session.add_all([feed, group, assoc])
        session.commit()

        delete_and_assert(
            session,
            [
                "SELECT COUNT(*) FROM osmlocationgroup where group_id = 'g1'",
                "SELECT COUNT(*) FROM feedlocationgrouppoint",
            ],
            group,
        )


def test_cascade_delete_osmlocationgroup_cascadeto_feedosmlocationgroup(test_database):
    with test_database.start_db_session() as session:
        feed = Feed(id="f1")
        group = Osmlocationgroup(group_id="g1", group_name="G1")
        assoc = Feedosmlocationgroup(feed_id="f1", group_id="g1", stops_count=1)
        session.add_all([feed, group, assoc])
        session.commit()

        delete_and_assert(
            session,
            [
                "SELECT COUNT(*) FROM osmlocationgroup where group_id = 'g1'",
                "SELECT COUNT(*) FROM feedosmlocationgroup",
            ],
            group,
        )


def test_cascade_delete_osmlocationgroup_cascadeto_osmlocationgroupgeopolygon(test_database):
    with test_database.start_db_session() as session:
        feed = Gtfsfeed(id="f1")
        group = Osmlocationgroup(group_id="g1", group_name="G1")
        geopolygon = Geopolygon(osm_id=1)
        group.osms.append(geopolygon)

        session.add_all([feed, group, geopolygon])
        session.commit()

        delete_and_assert(
            session,
            [
                "SELECT COUNT(*) FROM osmlocationgroup where group_id = 'g1'",
                "SELECT COUNT(*) FROM osmlocationgroupgeopolygon",
            ],
            group,
        )


def test_cascade_delete_validationreport_cascadeto_validationreportgtfsdataset(test_database):
    with test_database.start_db_session() as session:
        dataset = Gtfsdataset(id="d1")
        validationreport = Validationreport(id="v1")
        dataset.validation_reports.append(validationreport)

        session.add_all([dataset, validationreport])
        session.commit()

        delete_and_assert(
            session,
            [
                "SELECT COUNT(*) FROM validationreport where id = 'v1'",
                "SELECT COUNT(*) FROM validationreportgtfsdataset",
            ],
            validationreport,
        )


def test_delete_validationreport_cascadeto_featurevalidationreport(test_database):
    with test_database.start_db_session() as session:
        feature = Feature(name="f1")
        validationreport = Validationreport(id="v1")
        feature.validations.append(validationreport)

        session.add_all([feature, validationreport])
        session.commit()

        delete_and_assert(
            session,
            ["SELECT COUNT(*) FROM validationreport where id = 'v1'", "SELECT COUNT(*) FROM featurevalidationreport"],
            validationreport,
        )


def test_delete_validationreport_cascadeto_notice(test_database):
    with test_database.start_db_session() as session:
        dataset = Gtfsdataset(id="d1")
        validationreport = Validationreport(id="v1")
        notice = Notice(dataset_id="d1", notice_code="code1", total_notices=1, validation_report_id="v1")
        session.add_all([dataset, validationreport, notice])

        validationreport.notices.append(notice)
        session.commit()

        delete_and_assert(
            session, ["SELECT COUNT(*) FROM validationreport", "SELECT COUNT(*) FROM notice"], validationreport
        )
