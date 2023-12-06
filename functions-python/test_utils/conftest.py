import pytest

from database.database import Database
from feeds_gen.main import app as application
from .test_utils.database import populate_database


@pytest.fixture
def app() -> FastAPI:
    application.dependency_overrides = {}
    return application


@pytest.fixture(scope="session")
def test_database():
    with populate_database(Database()) as db:
        yield db


@pytest.fixture
def client(app, test_database) -> TestClient:
    return TestClient(app)
