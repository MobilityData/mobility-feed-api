#
#   MobilityData 2024
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

from shared.database_gen.sqlacodegen_models import (
    Redirectingid,
    Gtfsfeed,
    Gbfsfeed,
    Gtfsrealtimefeed,
)
from feeds_gen.models.redirect import Redirect
from shared.db_models.redirect_impl import RedirectImpl
from shared.helpers.query_helper import query_feed_by_stable_id


class OperationRedirectImpl(RedirectImpl, Redirect):
    """Implementation of the `Redirect` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    @classmethod
    def from_orm(cls, redirect: Redirectingid | None) -> Redirect | None:
        """
        Convert a SQLAlchemy row object to a Pydantic model.
        """
        if not redirect:
            return None
        return super().from_orm(redirect)

    @classmethod
    def to_orm(
        cls, redirect: Redirect, source: Gtfsfeed | Gtfsrealtimefeed | Gbfsfeed, session
    ) -> Redirectingid:
        """
        Convert a Pydantic model to a SQLAlchemy row object.
        """
        if not source or not source.id:
            raise ValueError("Invalid source object or source.id is not set")
        target_feed = query_feed_by_stable_id(
            session, redirect.target_id, source.data_type
        )

        if not target_feed or not target_feed.id:
            raise ValueError("Invalid target_feed object or target_feed.id is not set")

        return Redirectingid(
            source_id=source.id,
            target_id=target_feed.id,
            redirect_comment=redirect.comment,
        )
