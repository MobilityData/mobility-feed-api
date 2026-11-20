import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from feeds.impl.error_handling import raise_http_error
from garage_gen.apis.garage_api_base import BaseGarageApi
from garage_gen.models.signed_upload import SignedUpload
from garage_gen.models.upload_user_dataset_request import UploadUserDatasetRequest
from garage_gen.models.upload_user_dataset_response import UploadUserDatasetResponse
from garage_gen.models.user_dataset import UserDataset
from garage_gen.models.user_dataset_file import UserDatasetFile
from garage_gen.models.user_dataset_files import UserDatasetFiles
from garage_gen.models.user_dataset_status import UserDatasetStatus
from shared.common.error_handling import (
    endpoint_not_implemented,
    user_dataset_conversion_failed,
    user_dataset_not_found,
)
from shared.common import user_data_storage, user_task_state
from shared.common.user_data_retention import expires_at, expiry_cutoff
from shared.common.user_task_state import (
    TRACKER_COMPLETED,
    TRACKER_FAILED,
    TRACKER_IN_PROGRESS,
    TRACKER_TRIGGERED,
    TaskState,
)
from shared.database.users_database import with_users_db_session
from shared.users_database_gen.sqlacodegen_models import UserDataset as UserDatasetOrm
from shared.users_database_gen.sqlacodegen_models import UserTask as UserTaskOrm
from shared.users_database_gen.sqlacodegen_models import t_user_task_dataset
from user_service.impl.identity import require_user_id

TASK_KIND_GARAGE = "garage"
# The Garage task's output: a manifest describing the dataset, and one Parquet file per GTFS table.
MANIFEST_FILE_NAME = "manifest.json"
PARQUET_SUFFIX = ".parquet"

# How a Garage task's tracked state reads as the dataset's status. A task the tracker has no row
# for has not been triggered yet: its upload has not finished.
_STATUS_BY_TRACKER = {
    TRACKER_TRIGGERED: UserDatasetStatus.RUNNING,
    TRACKER_IN_PROGRESS: UserDatasetStatus.RUNNING,
    TRACKER_COMPLETED: UserDatasetStatus.READY,
    TRACKER_FAILED: UserDatasetStatus.FAILED,
}


class GarageApiImpl(BaseGarageApi):
    """
    Implementation of the `/v1/garage` endpoints.
    Access is checked by the `require_garage_access` dependency attached to the router before any of these
    run. Every query is scoped to the caller's user_id, so another user's dataset is reported as not found.

    Each uploaded dataset gets a `garage` user_task that converts it. The dataset's status, phase, progress and error
    come from that task's state in TaskExecutionTracker.
    """

    @with_users_db_session
    def get_user_datasets(self, limit: int, offset: int, db_session: Session) -> List[UserDataset]:
        rows = (
            _live_datasets(db_session, require_user_id())
            .order_by(UserDatasetOrm.created_at.desc(), UserDatasetOrm.id)
            .limit(limit)
            .offset(offset)
            .all()
        )
        task_ids = _garage_task_ids(db_session, [row.id for row in rows])
        states = user_task_state.task_states(TASK_KIND_GARAGE, list(task_ids.values()))
        return [_to_api(row, states.get(task_ids.get(row.id))) for row in rows]

    @with_users_db_session
    def upload_user_dataset(
        self, upload_user_dataset_request: UploadUserDatasetRequest, db_session: Session
    ) -> UploadUserDatasetResponse:
        user_id = require_user_id()
        now = datetime.now(timezone.utc)
        dataset = UserDatasetOrm(
            id=str(uuid.uuid4()), user_id=user_id, name=upload_user_dataset_request.name, created_at=now
        )
        db_session.add(
            UserTaskOrm(
                id=str(uuid.uuid4()), user_id=user_id, kind=TASK_KIND_GARAGE, created_at=now, datasets=[dataset]
            )
        )
        db_session.flush()
        # Signed after the insert so a failed insert never hands out a URL; a failed signature
        # rolls the insert back.
        upload = user_data_storage.sign_upload(user_id, dataset.id)
        return UploadUserDatasetResponse(
            dataset=_to_api(dataset, None),
            upload=SignedUpload(
                url=upload.url, method=upload.method, headers=upload.headers, expires_at=upload.expires_at
            ),
        )

    @with_users_db_session
    def get_user_dataset(self, id: str, db_session: Session) -> UserDataset:
        row = _live_datasets(db_session, require_user_id()).filter(UserDatasetOrm.id == id).one_or_none()
        if row is None:
            raise_http_error(404, user_dataset_not_found)
        task_id = _garage_task_ids(db_session, [row.id]).get(row.id)
        state = user_task_state.task_states(TASK_KIND_GARAGE, [task_id]).get(task_id) if task_id else None
        files = None
        if state is not None and state.status == TRACKER_COMPLETED:
            files = _garage_files(user_data_storage.task_files(row.user_id, task_id))
        return _to_api(row, state, files)

    def delete_user_dataset(self, id: str) -> None:
        raise_http_error(501, endpoint_not_implemented)


def _live_datasets(db_session: Session, user_id: str):
    """The user's datasets that have not expired.

    An expired dataset is gone from the API on its expiry date, before its files and row are deleted,
    so a user never sees a dataset that is being purged.
    """
    return db_session.query(UserDatasetOrm).filter(
        UserDatasetOrm.user_id == user_id,
        UserDatasetOrm.created_at > expiry_cutoff(),
    )


def _garage_task_ids(db_session: Session, dataset_ids: List[str]) -> Dict[str, str]:
    """The id of each dataset's `garage` task, keyed by dataset id. The newest wins if there are several."""
    if not dataset_ids:
        return {}
    rows = (
        db_session.query(t_user_task_dataset.c.dataset_id, UserTaskOrm.id)
        .join(UserTaskOrm, UserTaskOrm.id == t_user_task_dataset.c.task_id)
        .filter(t_user_task_dataset.c.dataset_id.in_(dataset_ids), UserTaskOrm.kind == TASK_KIND_GARAGE)
        .order_by(UserTaskOrm.created_at)
        .all()
    )
    return {dataset_id: task_id for dataset_id, task_id in rows}


def _garage_files(task_files: List[Tuple[str, str]]) -> Optional[UserDatasetFiles]:
    """The manifest and Parquet files of a Garage task's output, or None until the manifest exists."""
    urls = dict(task_files)
    if MANIFEST_FILE_NAME not in urls:
        return None
    return UserDatasetFiles(
        manifest_url=urls[MANIFEST_FILE_NAME],
        files=[UserDatasetFile(name=name, url=url) for name, url in task_files if name.endswith(PARQUET_SUFFIX)],
    )


def _to_api(row: UserDatasetOrm, state: Optional[TaskState], files: Optional[UserDatasetFiles] = None) -> UserDataset:
    status = UserDatasetStatus.PENDING_UPLOAD if state is None else _STATUS_BY_TRACKER[state.status]
    return UserDataset(
        id=row.id,
        name=row.name,
        status=status,
        phase=state.phase if status == UserDatasetStatus.RUNNING else None,
        progress=state.progress if status == UserDatasetStatus.RUNNING else None,
        # The tracker's error message is the worker's raw exception, not meant for users.
        error=user_dataset_conversion_failed if status == UserDatasetStatus.FAILED else None,
        size_bytes=row.size_bytes,
        created_at=row.created_at,
        expires_at=expires_at(row.created_at),
        files=files,
    )
