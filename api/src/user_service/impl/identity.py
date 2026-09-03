"""Shared identity helper for User Service impls.

Extracted from `UsersApiImpl._require_user_id` (which now delegates here) so other impls don't
need to import a sibling impl class just to resolve the caller's identity.
"""

from fastapi import HTTPException

from middleware.request_context import get_request_context


def require_user_id() -> str:
    """Return the authenticated, non-guest caller's user_id.

    Raises 401 if no identity could be resolved from the token, and 403 for a guest (guests have
    no `app_user` row and cannot own anything user-scoped).
    """
    context = get_request_context()
    user_id = context.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unable to determine user identity from token.")
    if context.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guest users cannot perform this action.")
    return user_id
