"""Object names in the user data buckets, shared by the API and the functions that run users' tasks.

Layout, the same in both buckets so everything of a user's sits under one prefix:
    datasets bucket (USER_DATASETS_BUCKET_NAME), private:
        <user_key>/uploads/<dataset_id>/source.zip   the file the user uploads through a signed URL
    task outputs bucket (USER_TASK_OUTPUTS_BUCKET_NAME), public:
        <user_key>/tasks/<task_id>/...               a task's output, readable by anyone with the URL

`user_key` is derived from the user id so a user's objects are grouped without the user id itself
appearing in object names, which URLs expose. It is a plain hash rather than an HMAC: user ids are
random Firebase UIDs, so the key cannot be reversed by guessing, and no secret has to be shared and
kept forever. Never change the derivation: it would orphan every object. The key is stable, so
anyone who sees two public URLs of the same user can tell they belong to the same user.

The task outputs bucket cannot be listed and the task id is a random UUID, so a public URL cannot be
guessed, even knowing the user key. Outputs belong to the task, not to a dataset, since a task can
work on several datasets and a dataset can be used by several tasks.
"""

import hashlib

UPLOADS_PREFIX = "uploads"
TASKS_PREFIX = "tasks"
UPLOAD_FILE_NAME = "source.zip"


def user_storage_key(user_id: str) -> str:
    """The key that stands in for the user id in object names."""
    return hashlib.sha256(f"user-data:{user_id}".encode()).hexdigest()[:32]


def user_prefix(user_id: str) -> str:
    """The prefix holding all of the user's objects, in either bucket, with a trailing slash."""
    return f"{user_storage_key(user_id)}/"


def dataset_upload_prefix(user_id: str, dataset_id: str) -> str:
    """The prefix holding the dataset's upload in the datasets bucket, with a trailing slash."""
    return f"{user_prefix(user_id)}{UPLOADS_PREFIX}/{dataset_id}/"


def upload_object_name(user_id: str, dataset_id: str) -> str:
    """Where the user uploads the dataset's file."""
    return f"{dataset_upload_prefix(user_id, dataset_id)}{UPLOAD_FILE_NAME}"


def task_files_prefix(user_id: str, task_id: str) -> str:
    """The prefix holding the task's output in the task outputs bucket, with a trailing slash."""
    return f"{user_prefix(user_id)}{TASKS_PREFIX}/{task_id}/"
