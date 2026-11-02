import os
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from main import app as application
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import Gbfsfeed, Gtfsfeed, Gtfsrealtimefeed, Location
from tests.test_utils.database import populate_database

# Declared locations: id -> (country_code, country, subdivision_name, municipality).
LOCATIONS = {
    "ca": ("CA", "Canada", None, None),
    # Lowercase code and blank subdivision: normalized to a country-only location.
    "ca-blank": ("ca", "Canada", "", None),
    "ca-quebec": ("CA", "Canada", "Québec", None),
    # Another spelling of Québec: same slug, so the same node.
    "ca-quebec-unaccented": ("CA", "Canada", "Quebec", None),
    "ca-quebec-montreal": ("CA", "Canada", "Québec", "Montréal"),
    "ca-quebec-laval": ("CA", "Canada", "Quebec", "Laval"),
    "ca-ontario-toronto": ("CA", "Canada", "Ontario", "Toronto"),
    # Municipality without subdivision: counts toward Canada only.
    "ca-whistler": ("CA", "Canada", None, "Whistler"),
    "us-new-york": ("US", "United States", "New York", "New York City"),
    "fr-idf-paris": ("FR", "France", "Île-de-France", "Paris"),
    "xk-pristina": ("XK", "Kosovo", None, "Pristina"),
    # Not in the continent mapping: left out of the directory.
    "zz": ("ZZ", "Nowhere", None, None),
}

# Feeds: (stable_id, model, data_type, status, operational_status, provider, feed_name, location ids).
FEEDS = [
    ("ld-1", Gtfsfeed, "gtfs", "active", "published", "A Provider", "Quebec wide", ["ca-quebec"]),
    ("ld-2", Gtfsfeed, "gtfs", "active", "published", "B Provider", "Montreal metro", ["ca-quebec-montreal"]),
    (
        "ld-3",
        Gtfsrealtimefeed,
        "gtfs_rt",
        "active",
        "published",
        "A Provider",
        "Montreal and Laval",
        ["ca-quebec-montreal", "ca-quebec-laval"],
    ),
    ("ld-4", Gbfsfeed, "gbfs", "active", "published", "C Provider", "Bikes", ["ca-quebec-unaccented"]),
    ("ld-5", Gtfsfeed, "gtfs", "inactive", "published", "D Provider", "Canada wide", ["ca"]),
    ("ld-6", Gtfsfeed, "gtfs", "deprecated", "published", "E Provider", "Deprecated", ["ca-quebec-montreal"]),
    ("ld-7", Gtfsfeed, "gtfs", "active", "wip", "E Provider", "Work in progress", ["ca-quebec-montreal"]),
    ("ld-8", Gtfsfeed, "gtfs", "future", "published", "F Provider", "Whistler", ["ca-whistler"]),
    (
        "ld-9",
        Gtfsfeed,
        "gtfs",
        "development",
        "published",
        "H Provider",
        "Cross border",
        ["ca-ontario-toronto", "us-new-york"],
    ),
    ("ld-10", Gtfsfeed, "gtfs", "active", "published", "I Provider", "Paris", ["fr-idf-paris"]),
    ("ld-11", Gtfsfeed, "gtfs", "active", "published", "J Provider", "Pristina", ["xk-pristina"]),
    ("ld-12", Gtfsfeed, "gtfs", "active", "published", "K Provider", "Nowhere", ["zz"]),
    ("ld-13", Gtfsfeed, "gtfs", "active", "published", "G Provider", "Canada blank", ["ca-blank"]),
]


def _populate_location_directory_data(db: Database):
    created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with db.start_db_session() as session:
        locations = {
            location_id: Location(
                id=location_id,
                country_code=country_code,
                country=country,
                subdivision_name=subdivision_name,
                municipality=municipality,
            )
            for location_id, (country_code, country, subdivision_name, municipality) in LOCATIONS.items()
        }
        for stable_id, model, data_type, status, operational_status, provider, feed_name, location_ids in FEEDS:
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
                    locations=[locations[location_id] for location_id in location_ids],
                )
            )
        session.flush()
        session.execute(text("REFRESH MATERIALIZED VIEW feedsearch"))
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
