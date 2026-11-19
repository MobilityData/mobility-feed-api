from fastapi import HTTPException

from shared.common.error_handling import garage_not_permitted
from shared.common.feature_flags import feature_flag_enabled
from shared.database.users_database import UsersDatabase
from user_service.impl.identity import require_user_id

# Feature flag (feature_flag.id, users database) that grants a user access to their datasets in the Garage.
# Internal only: the API never names it to clients.
USER_DATASETS_FEATURE_FLAG_ID = "userDatasets"


def require_garage_access() -> str:
    """FastAPI dependency guarding every `/v1/garage` route.

    Returns the caller's user_id. Raises 401/403 through `require_user_id` when there is no
    identity or the caller is a guest, and 403 when the user does not hold the user datasets
    feature flag.
    """
    user_id = require_user_id()
    with UsersDatabase().start_db_session() as db_session:
        if not feature_flag_enabled(db_session, user_id, USER_DATASETS_FEATURE_FLAG_ID):
            raise HTTPException(status_code=403, detail=garage_not_permitted)
    return user_id
