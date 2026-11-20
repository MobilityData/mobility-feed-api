"""DB-backed tests for the Garage dataset endpoints, against the real test databases.

The access check and the bucket are mocked; the queries run for real, so the user scoping, the
expiry filter and the task state read from the tracker are tested against Postgres.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from garage.impl.garage_api_impl import TASK_KIND_GARAGE
from main import app
from shared.common import user_data_storage
from shared.common.error_handling import user_dataset_conversion_failed
from shared.database.database import Database
from shared.database.users_database import UsersDatabase
from shared.database_gen.sqlacodegen_models import TaskExecutionLog
from shared.users_database_gen.sqlacodegen_models import AppUser, UserDataset, UserTask

# Test databases, matching the Liquibase targets in the CI "Run tests" job.
USERS_TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseUsersTest"
FEEDS_TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:54320/MobilityDatabaseTest"
SIGNED_UPLOAD = user_data_storage.SignedUpload(
    url="https://storage.googleapis.com/signed-put",
    method="PUT",
    headers={"Content-Type": "application/zip", "x-goog-content-length-range": "1,100"},
    expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
)


def _reset_singletons():
    for database in (UsersDatabase, Database):
        database.instance = None
        database.initialized = False


@pytest.fixture
def db(monkeypatch):
    """Point the API at the test databases, and reset the singletons around the test."""
    monkeypatch.setenv("USERS_DATABASE_URL", os.getenv("TEST_USERS_DATABASE_URL", USERS_TEST_DATABASE_URL))
    monkeypatch.setenv("FEEDS_DATABASE_URL", os.getenv("TEST_FEEDS_DATABASE_URL", FEEDS_TEST_DATABASE_URL))
    _reset_singletons()
    try:
        yield UsersDatabase()
    finally:
        _reset_singletons()


@pytest.fixture
def make_user(db):
    """Creates users on demand and deletes them, with their datasets and tasks, after the test."""
    user_ids = []

    def make():
        user_id = f"user-{uuid.uuid4().hex}"
        with db.start_db_session() as session:
            session.add(AppUser(id=user_id, email=f"{user_id}@example.com"))
        user_ids.append(user_id)
        return user_id

    yield make
    with db.start_db_session() as session:
        session.query(AppUser).filter(AppUser.id.in_(user_ids)).delete(synchronize_session=False)


@pytest.fixture
def track(db):
    """Records a task's state in the tracker, as the worker would, and deletes it after the test."""
    task_ids = []

    def record(task_id, status, metadata=None, run_id="1", triggered_at=None):
        with Database().start_db_session() as session:
            session.add(
                TaskExecutionLog(
                    task_name=TASK_KIND_GARAGE,
                    entity_id=task_id,
                    run_id=run_id,
                    status=status,
                    metadata_=metadata,
                    error_message="Traceback: internal detail",
                    triggered_at=triggered_at or datetime.now(),
                )
            )
        task_ids.append(task_id)

    yield record
    with Database().start_db_session() as session:
        session.query(TaskExecutionLog).filter(TaskExecutionLog.entity_id.in_(task_ids)).delete(
            synchronize_session=False
        )


@pytest.fixture(autouse=True)
def retention_30_days(monkeypatch):
    monkeypatch.setenv("USER_DATA_RETENTION_DAYS", "30")


@pytest.fixture(autouse=True)
def garage_access():
    """Grant every caller the Garage flag; access itself is tested separately."""
    with patch("garage.impl.garage_access.UsersDatabase") as users_database, patch(
        "garage.impl.garage_access.feature_flag_enabled", return_value=True
    ):
        users_database.return_value.start_db_session.return_value.__enter__.return_value = MagicMock()
        yield


def _headers(user_id):
    return {"x-goog-authenticated-user-id": f"accounts.google.com:{user_id}"}


def _add_dataset(db, user_id, name="feed", created_at=None):
    """Adds a dataset and its Garage task, as the upload does. Returns (dataset id, task id)."""
    created_at = created_at or datetime.now(timezone.utc)
    dataset = UserDataset(id=str(uuid.uuid4()), user_id=user_id, name=name, created_at=created_at)
    task = UserTask(
        id=str(uuid.uuid4()), user_id=user_id, kind=TASK_KIND_GARAGE, created_at=created_at, datasets=[dataset]
    )
    dataset_id, task_id = dataset.id, task.id
    with db.start_db_session() as session:
        session.add(task)
    return dataset_id, task_id


client = TestClient(app)


class TestUpload:
    def test_creates_dataset_and_garage_task_and_returns_signed_upload(self, db, make_user):
        user_id = make_user()
        with patch.object(user_data_storage, "sign_upload", return_value=SIGNED_UPLOAD) as sign_upload:
            response = client.post("/v1/garage/datasets:upload", json={"name": "my feed"}, headers=_headers(user_id))

        assert response.status_code == 201
        body = response.json()
        assert body["dataset"]["name"] == "my feed"
        assert body["dataset"]["status"] == "pending_upload"
        assert body["upload"]["url"] == SIGNED_UPLOAD.url
        assert body["upload"]["method"] == "PUT"
        assert body["upload"]["headers"] == SIGNED_UPLOAD.headers
        sign_upload.assert_called_once_with(user_id, body["dataset"]["id"])
        with db.start_db_session() as session:
            dataset = session.get(UserDataset, body["dataset"]["id"])
            assert dataset.user_id == user_id
            assert [(task.kind, task.user_id) for task in dataset.tasks] == [(TASK_KIND_GARAGE, user_id)]

    def test_signing_failure_creates_nothing(self, db, make_user):
        user_id = make_user()
        failing_client = TestClient(app, raise_server_exceptions=False)
        with patch.object(user_data_storage, "sign_upload", side_effect=RuntimeError("IAM unavailable")):
            response = failing_client.post(
                "/v1/garage/datasets:upload", json={"name": "my feed"}, headers=_headers(user_id)
            )

        assert response.status_code == 500
        with db.start_db_session() as session:
            assert session.query(UserDataset).filter(UserDataset.user_id == user_id).count() == 0
            assert session.query(UserTask).filter(UserTask.user_id == user_id).count() == 0


class TestList:
    def test_returns_own_live_datasets_newest_first(self, db, make_user):
        user_id, other_user_id = make_user(), make_user()
        now = datetime.now(timezone.utc)
        older, _ = _add_dataset(db, user_id, "older", created_at=now - timedelta(days=2))
        newer, _ = _add_dataset(db, user_id, "newer", created_at=now - timedelta(days=1))
        _add_dataset(db, user_id, "expired", created_at=now - timedelta(days=31))
        _add_dataset(db, other_user_id, "not mine")

        response = client.get("/v1/garage/datasets", headers=_headers(user_id))

        assert response.status_code == 200
        assert [dataset["id"] for dataset in response.json()] == [newer, older]
        assert all(dataset["files"] is None for dataset in response.json())

    def test_status_comes_from_the_tracker(self, db, make_user, track):
        user_id = make_user()
        now = datetime.now(timezone.utc)
        pending, _ = _add_dataset(db, user_id, created_at=now - timedelta(minutes=4))
        triggered, triggered_task = _add_dataset(db, user_id, created_at=now - timedelta(minutes=3))
        running, running_task = _add_dataset(db, user_id, created_at=now - timedelta(minutes=2))
        ready, ready_task = _add_dataset(db, user_id, created_at=now - timedelta(minutes=1))
        failed, failed_task = _add_dataset(db, user_id, created_at=now)
        retrying, retrying_task = _add_dataset(db, user_id, created_at=now - timedelta(minutes=5))
        track(triggered_task, "triggered")
        track(running_task, "in_progress", metadata={"phase": "converting(stops.txt)", "done": 2, "total": 5})
        # A finished task keeps its last heartbeat; the API must not show it.
        track(ready_task, "completed", metadata={"phase": "converting(trips.txt)", "done": 5, "total": 5})
        track(failed_task, "failed", metadata={"phase": "converting(stops.txt)", "final": True})
        track(retrying_task, "failed", metadata={"phase": "converting(stops.txt)", "done": 1, "total": 5})

        response = client.get("/v1/garage/datasets", headers=_headers(user_id))

        by_id = {dataset["id"]: dataset for dataset in response.json()}
        assert by_id[pending]["status"] == "pending_upload"
        assert by_id[triggered]["status"] == "running"
        assert by_id[triggered]["phase"] is None and by_id[triggered]["progress"] is None
        assert by_id[running]["status"] == "running"
        assert by_id[running]["phase"] == "converting(stops.txt)" and by_id[running]["progress"] == 40
        assert by_id[ready]["status"] == "ready"
        assert by_id[ready]["phase"] is None and by_id[ready]["progress"] is None
        assert by_id[failed]["status"] == "failed"
        assert by_id[failed]["error"] == user_dataset_conversion_failed
        assert by_id[failed]["phase"] is None
        # Not final: waiting for a retry, and its last phase is stale.
        assert by_id[retrying]["status"] == "running" and by_id[retrying]["error"] is None
        assert by_id[retrying]["phase"] is None and by_id[retrying]["progress"] is None

    def test_unknown_tracker_status_reads_as_running(self, db, make_user, track):
        user_id = make_user()
        _, task_id = _add_dataset(db, user_id)
        track(task_id, "some_future_status")

        response = client.get("/v1/garage/datasets", headers=_headers(user_id))

        assert response.status_code == 200
        assert response.json()[0]["status"] == "running"

    def test_latest_tracker_run_wins(self, db, make_user, track):
        user_id = make_user()
        _, task_id = _add_dataset(db, user_id)
        track(task_id, "failed", run_id="1", triggered_at=datetime.now() - timedelta(hours=1))
        track(task_id, "completed", run_id="2")

        response = client.get("/v1/garage/datasets", headers=_headers(user_id))

        assert response.json()[0]["status"] == "ready"

    def test_limit_and_offset(self, db, make_user):
        user_id = make_user()
        now = datetime.now(timezone.utc)
        ids = [_add_dataset(db, user_id, f"feed {i}", created_at=now - timedelta(minutes=i))[0] for i in range(3)]

        response = client.get("/v1/garage/datasets?limit=1&offset=1", headers=_headers(user_id))

        assert [dataset["id"] for dataset in response.json()] == [ids[1]]


class TestSchema:
    def test_a_dataset_used_by_a_task_cannot_be_deleted(self, db, make_user):
        dataset_id, _ = _add_dataset(db, make_user())
        with pytest.raises(IntegrityError):
            with db.start_db_session() as session:
                session.query(UserDataset).filter(UserDataset.id == dataset_id).delete()

    def test_deleting_a_user_deletes_their_datasets_and_tasks(self, db, make_user):
        user_id = make_user()
        dataset_id, task_id = _add_dataset(db, user_id)
        with db.start_db_session() as session:
            session.query(AppUser).filter(AppUser.id == user_id).delete()
        with db.start_db_session() as session:
            assert session.get(UserDataset, dataset_id) is None
            assert session.get(UserTask, task_id) is None


class TestGet:
    def test_returns_own_dataset_without_files_until_ready(self, db, make_user):
        user_id = make_user()
        dataset_id, _ = _add_dataset(db, user_id, "mine")
        with patch.object(user_data_storage, "task_files") as task_files:
            response = client.get(f"/v1/garage/datasets/{dataset_id}", headers=_headers(user_id))

        assert response.status_code == 200
        assert response.json()["name"] == "mine"
        assert response.json()["status"] == "pending_upload"
        created_at = datetime.fromisoformat(response.json()["created_at"])
        assert datetime.fromisoformat(response.json()["expires_at"]) == created_at + timedelta(days=30)
        assert response.json()["files"] is None
        task_files.assert_not_called()

    def test_ready_dataset_returns_its_manifest_and_parquet_urls(self, db, make_user, track):
        user_id = make_user()
        dataset_id, task_id = _add_dataset(db, user_id)
        track(task_id, "completed")
        stored = [
            ("manifest.json", "https://storage.googleapis.com/manifest"),
            ("notes.txt", "https://storage.googleapis.com/notes"),
            ("stops.parquet", "https://storage.googleapis.com/stops"),
        ]
        with patch.object(user_data_storage, "task_files", return_value=stored) as task_files:
            response = client.get(f"/v1/garage/datasets/{dataset_id}", headers=_headers(user_id))

        assert response.status_code == 200
        assert response.json()["status"] == "ready"
        assert response.json()["files"] == {
            "manifest_url": "https://storage.googleapis.com/manifest",
            "files": [{"name": "stops.parquet", "url": "https://storage.googleapis.com/stops"}],
        }
        task_files.assert_called_once_with(user_id, task_id)

    def test_ready_dataset_without_manifest_has_no_files(self, db, make_user, track):
        user_id = make_user()
        dataset_id, task_id = _add_dataset(db, user_id)
        track(task_id, "completed")
        stored = [("stops.parquet", "https://storage.googleapis.com/stops")]
        with patch.object(user_data_storage, "task_files", return_value=stored):
            response = client.get(f"/v1/garage/datasets/{dataset_id}", headers=_headers(user_id))

        assert response.status_code == 200
        assert response.json()["files"] is None

    def test_another_users_dataset_is_404(self, db, make_user):
        user_id, other_user_id = make_user(), make_user()
        dataset_id, _ = _add_dataset(db, other_user_id)

        response = client.get(f"/v1/garage/datasets/{dataset_id}", headers=_headers(user_id))

        assert response.status_code == 404

    def test_expired_dataset_is_404(self, db, make_user):
        user_id = make_user()
        dataset_id, _ = _add_dataset(db, user_id, created_at=datetime.now(timezone.utc) - timedelta(days=31))

        response = client.get(f"/v1/garage/datasets/{dataset_id}", headers=_headers(user_id))

        assert response.status_code == 404

    def test_unknown_dataset_is_404(self, db, make_user):
        response = client.get(f"/v1/garage/datasets/{uuid.uuid4()}", headers=_headers(make_user()))
        assert response.status_code == 404
