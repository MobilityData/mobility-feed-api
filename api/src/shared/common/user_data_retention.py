"""How long users' datasets and tasks are kept, shared by the API and the job that purges them.

A dataset or task expires USER_DATA_RETENTION_DAYS after it is created. The expiry is computed from
the current setting rather than stored on the row, so changing the period applies to every row, as
the buckets' lifecycle rule does to the files. The setting comes from the same Terraform variable
as that rule, which waits a margin past the retention so it never deletes live files.
"""

import os
from datetime import datetime, timedelta, timezone

DEFAULT_RETENTION_DAYS = 30


def retention() -> timedelta:
    return timedelta(days=int(os.getenv("USER_DATA_RETENTION_DAYS", DEFAULT_RETENTION_DAYS)))


def expires_at(created_at: datetime) -> datetime:
    """When a row created at `created_at` expires."""
    return created_at + retention()


def expiry_cutoff() -> datetime:
    """Rows created at or before this moment have expired."""
    return datetime.now(timezone.utc) - retention()
