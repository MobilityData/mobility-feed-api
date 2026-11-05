import os
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import insert, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from main import app as application
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import (
    Continent,
    CountryContinent,
    Feedosmlocationgroup,
    Gbfsfeed,
    Geopolygon,
    Geopolygonhierarchy,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Osmlocationgroup,
    t_feedreference,
    t_osmlocationgroupgeopolygon,
)
from tests.test_utils.database import populate_database

# The continent and country_continent rows are seeded by Liquibase, but other test packages truncate every table,
# so the rows used here are inserted again when missing. CP (Clipperton) has no continent in the classification.
CONTINENTS = [
    ("AF", "africa", "Africa"),
    ("AN", "antarctica", "Antarctica"),
    ("AS", "asia", "Asia"),
    ("EU", "europe", "Europe"),
    ("NA", "north-america", "North America"),
    ("OC", "oceania", "Oceania"),
    ("SA", "south-america", "South America"),
]
COUNTRY_CONTINENTS = {"CA": "NA", "US": "NA", "MQ": "NA", "FR": "EU"}

# Geopolygons: osm_id -> (admin_level, name, iso_3166_1_code, iso_3166_2_code, parent osm_id).
GEOPOLYGONS = {
    1: (2, "Canada", "CA", None, None),
    2: (4, "Québec", None, "CA-QC", 1),
    3: (6, "Montréal (région)", None, None, 2),
    4: (8, "Montréal", None, None, 3),
    5: (8, "Laval", None, None, 2),
    6: (4, "Ontario", None, "CA-ON", 1),
    7: (8, "Toronto", None, None, 6),
    # Same name under the same parent: both get the -<osm_id> suffix.
    8: (8, "Springfield", None, None, 6),
    9: (8, "Springfield", None, None, 6),
    10: (2, "United States", "US", None, None),
    11: (4, "New York", None, "US-NY", 10),
    12: (8, "New York City", None, None, 11),
    20: (2, "France", "FR", None, None),
    21: (4, "Île-de-France", None, "FR-IDF", 20),
    22: (8, "Paris", None, None, 21),
    # Two boundaries of the same country: only the lowest admin level is a location.
    30: (3, "Martinique", "MQ", None, None),
    31: (4, "Martinique", "MQ", None, None),
    # A country without continent in the classification.
    50: (2, "Clipperton", "CP", None, None),
}

# Location groups: the chain of areas covering some stops, from the country down.
GROUPS = {
    "g-montreal": [1, 2, 3, 4],
    "g-laval": [1, 2, 5],
    "g-quebec": [1, 2],
    "g-toronto": [1, 6, 7],
    "g-nyc": [10, 11, 12],
    "g-paris": [20, 21, 22],
    "g-martinique": [30],
    "g-clipperton": [50],
}

# Feeds: (stable_id, model, data_type, status, operational_status, provider, feed_name, {group_id: stops_count}).
FEEDS = [
    ("ld-1", Gtfsfeed, "gtfs", "active", "published", "A Provider", "Montreal bus", {"g-montreal": 100}),
    (
        "ld-2",
        Gtfsrealtimefeed,
        "gtfs_rt",
        "active",
        "published",
        "B Provider",
        "Quebec train",
        {"g-montreal": 20, "g-laval": 30, "g-quebec": 50},
    ),
    ("ld-3", Gbfsfeed, "gbfs", "active", "published", "C Provider", "Bikes", {"g-montreal": 50, "g-laval": 50}),
    ("ld-4", Gtfsfeed, "gtfs", "inactive", "published", "D Provider", "Cross border", {"g-toronto": 75, "g-nyc": 25}),
    ("ld-5", Gtfsfeed, "gtfs", "deprecated", "published", "E Provider", "Deprecated", {"g-montreal": 10}),
    ("ld-6", Gtfsfeed, "gtfs", "active", "wip", "F Provider", "Work in progress", {"g-montreal": 10}),
    ("ld-7", Gtfsfeed, "gtfs", "future", "published", "G Provider", "Paris", {"g-paris": 40}),
    ("ld-8", Gtfsfeed, "gtfs", "development", "published", "H Provider", "Martinique", {"g-martinique": 5}),
    ("ld-9", Gtfsfeed, "gtfs", "active", "published", "I Provider", "Clipperton", {"g-clipperton": 1}),
    # Never geolocated: in no location.
    ("ld-10", Gtfsfeed, "gtfs", "active", "published", "J Provider", "Not geolocated", {}),
    # No stop count: its share of stops in a location is unknown, so it ranks last.
    ("ld-11", Gtfsfeed, "gtfs", "active", "published", "A Provider", "Montreal metro", {"g-montreal": 0}),
    # Realtime feed never geolocated: it takes the location of the schedule feed it references (ld-7, Paris).
    ("ld-12", Gtfsrealtimefeed, "gtfs_rt", "active", "published", "G Provider", "Paris realtime", {}),
    # Realtime feed with its own location (Paris): it does not take the location of ld-1 (Montreal).
    ("ld-13", Gtfsrealtimefeed, "gtfs_rt", "active", "published", "K Provider", "Paris vehicles", {"g-paris": 5}),
]

# Feed references: (realtime feed, schedule feed).
FEED_REFERENCES = [("ld-12", "ld-7"), ("ld-13", "ld-1")]


def _populate_location_directory_data(db: Database):
    created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with db.start_db_session() as session:
        session.execute(
            pg_insert(Continent)
            .values([{"code": code, "slug": slug, "name": name} for code, slug, name in CONTINENTS])
            .on_conflict_do_nothing()
        )
        session.execute(
            pg_insert(CountryContinent)
            .values(
                [
                    {"country_code": country_code, "continent_code": continent_code}
                    for country_code, continent_code in COUNTRY_CONTINENTS.items()
                ]
            )
            .on_conflict_do_nothing()
        )
        for osm_id, (admin_level, name, iso_3166_1_code, iso_3166_2_code, _) in GEOPOLYGONS.items():
            session.add(
                Geopolygon(
                    osm_id=osm_id,
                    admin_level=admin_level,
                    name=name,
                    iso_3166_1_code=iso_3166_1_code,
                    iso_3166_2_code=iso_3166_2_code,
                )
            )
        session.flush()
        for osm_id, (_, _, _, _, parent_osm_id) in GEOPOLYGONS.items():
            if parent_osm_id is not None:
                session.add(Geopolygonhierarchy(osm_id=osm_id, parent_osm_id=parent_osm_id))
        for group_id in GROUPS:
            session.add(Osmlocationgroup(group_id=group_id, group_name=group_id))
        session.flush()
        session.execute(
            insert(t_osmlocationgroupgeopolygon).values(
                [{"group_id": group_id, "osm_id": osm_id} for group_id, osm_ids in GROUPS.items() for osm_id in osm_ids]
            )
        )
        for stable_id, model, data_type, status, operational_status, provider, feed_name, groups in FEEDS:
            session.add(
                model(
                    id=f"id-{stable_id}",
                    stable_id=stable_id,
                    data_type=data_type,
                    status=status,
                    operational_status=operational_status,
                    provider=provider,
                    feed_name=feed_name,
                    created_at=created_at,
                )
            )
        session.flush()
        for stable_id, *_, groups in FEEDS:
            for group_id, stops_count in groups.items():
                session.add(Feedosmlocationgroup(feed_id=f"id-{stable_id}", group_id=group_id, stops_count=stops_count))
        session.execute(
            insert(t_feedreference).values(
                [
                    {"gtfs_rt_feed_id": f"id-{realtime_id}", "gtfs_feed_id": f"id-{schedule_id}"}
                    for realtime_id, schedule_id in FEED_REFERENCES
                ]
            )
        )
        session.flush()
        session.execute(text("REFRESH MATERIALIZED VIEW feedsearch"))
        session.execute(text("REFRESH MATERIALIZED VIEW geopolygonlocationsearch"))
        session.commit()


@pytest.fixture(scope="package")
def app() -> FastAPI:
    application.dependency_overrides = {}
    return application


@pytest.fixture(scope="package")
def test_database():
    # Restrict the tests to the test database
    os.environ["FEEDS_DATABASE_URL"] = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseTest"

    with populate_database(Database(), []) as db:
        _populate_location_directory_data(db)
        yield db


@pytest.fixture(scope="package")
def client(app, test_database) -> TestClient:
    return TestClient(app)
