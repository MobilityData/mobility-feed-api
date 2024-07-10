import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.database import Database
from main import app as application
from .test_utils.database import populate_database


@pytest.fixture
def app() -> FastAPI:
    application.dependency_overrides = {}
    return application


@pytest.fixture(scope="session")
def test_database():
    # Restrict the tests to the test database
    os.environ["FEEDS_DATABASE_URL"] = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseTest"
    with populate_database(Database()) as db:
        yield db


@pytest.fixture
def client(app, test_database) -> TestClient:
    return TestClient(app)
