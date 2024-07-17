import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.database import Database
from main import app as application
from tests.test_utils.database import populate_database


@pytest.fixture
def app() -> FastAPI:
    application.dependency_overrides = {}
    return application


@pytest.fixture(scope="module")
def test_database():

    # Restrict the tests to the test database
    os.environ["FEEDS_DATABASE_URL"] = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseTest"

    current_path = os.path.dirname(os.path.abspath(__file__))

    data_dirs = [current_path + "/../test_data"]

    with populate_database(Database(), data_dirs) as db:
        yield db


@pytest.fixture
def client(app, test_database) -> TestClient:
    return TestClient(app)
