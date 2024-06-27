import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .database import Database
from main import app as application
from .database import populate_database


@pytest.fixture
def app() -> FastAPI:
    application.dependency_overrides = {}
    return application


# Using scope package so the DB is emptied before executing the tests outside this directory.
@pytest.fixture(scope="package")
def test_database():
    with populate_database(Database()) as db:
        yield db


@pytest.fixture
def client(app, test_database) -> TestClient:
    return TestClient(app)
