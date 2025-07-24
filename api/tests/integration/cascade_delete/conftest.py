import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from shared.database.database import Database
from main import app as application
from tests.test_utils.database import populate_database


@pytest.fixture(scope="package")
def app() -> FastAPI:
    application.dependency_overrides = {}
    return application


@pytest.fixture(scope="package")
def test_database():
    # Restrict the tests to the test database
    os.environ["FEEDS_DATABASE_URL"] = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseTest"

    data_dirs = []
    second_phase_data_dirs = []
    with populate_database(Database(), data_dirs, second_phase_data_dirs) as db:
        yield db


@pytest.fixture(scope="package")
def client(app, test_database) -> TestClient:
    return TestClient(app)


# We want to delete all data from the database after each test so we don't have to coordinate the DB ids between tests.
@pytest.fixture(autouse=True)
def clean_database(test_database, request):
    yield
    # Check if the test passed
    if request.node.rep_call.outcome == "passed":
        with test_database.start_db_session() as session:
            for table in session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")):
                session.execute(text(f"TRUNCATE {table[0]} CASCADE"))
            session.commit()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # Attach test result to the request object
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{call.when}", report)
