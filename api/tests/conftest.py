import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.database import Database
from database_gen.sqlacodegen_models import Gtfsfeed, Gtfsrealtimefeed
from feeds_gen.main import app as application

FAKE_GTFS_FEED_STABLE_ID = "mdb-1"
FAKE_GTFS_RT_FEED_STABLE_ID = "mdb-1561"


@pytest.fixture
def app() -> FastAPI:
    application.dependency_overrides = {}
    db = Database()
    db.merge(Gtfsfeed(id=uuid.uuid4(), stable_id=FAKE_GTFS_FEED_STABLE_ID, data_type="gtfs", status="active"))
    db.merge(
        Gtfsrealtimefeed(id=uuid.uuid4(), stable_id=FAKE_GTFS_RT_FEED_STABLE_ID, data_type="gtfs_rt", status="active")
    )
    db.commit()
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)
