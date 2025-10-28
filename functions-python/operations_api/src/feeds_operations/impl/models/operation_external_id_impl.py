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
    Externalid,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Gbfsfeed,
)
from feeds_gen.models.external_id import ExternalId
from shared.db_models.external_id_impl import ExternalIdImpl


class OperationExternalIdImpl(ExternalIdImpl, ExternalId):
    """Implementation of the `ExternalId` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    @classmethod
    def from_orm(cls, external_id: Externalid | None) -> ExternalId | None:
        """
        Convert a SQLAlchemy row object to a Pydantic model
        """
        if not external_id:
            return None
        return super().from_orm(external_id)

    @classmethod
    def to_orm(
        cls, external_id: ExternalId, feed: Gtfsfeed | Gtfsrealtimefeed | Gbfsfeed
    ) -> Externalid:
        """
        Convert a Pydantic model to a SQLAlchemy row object
        """
        return Externalid(
            feed_id=feed.id,
            associated_id=external_id.external_id,
            source=external_id.source,
        )
