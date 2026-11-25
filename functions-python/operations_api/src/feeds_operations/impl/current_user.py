#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from fastapi import HTTPException
from sqlalchemy import func

from middleware.request_context_oauth2 import get_request_context
from shared.users_database_gen.sqlacodegen_models import AppUser


def current_app_user(db_session, *options) -> AppUser:
    """
    The Mobility Database user signed in to the Operations API.

    The caller is identified by the email of their validated Google token, matched
    case-insensitively to ``app_user.email``; each email belongs to at most one user.
    ``options`` are passed to the query (e.g. eager loads).

    raises:
        HTTPException: 401, if the request carries no user email.
        HTTPException: 404, if no user has the caller's email.
    """
    email = (get_request_context().get("user_email") or "").strip()
    # Locally the email comes from x-goog-authenticated-user-email, which IAP prefixes
    # with "accounts.google.com:".
    email = email.split(":")[-1].lower()
    if not email:
        raise HTTPException(status_code=401, detail="The request has no user email.")
    user = (
        db_session.query(AppUser)
        .options(*options)
        .filter(func.lower(AppUser.email) == email)
        .one_or_none()
    )
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="No Mobility Database user has the signed-in email.",
        )
    return user
