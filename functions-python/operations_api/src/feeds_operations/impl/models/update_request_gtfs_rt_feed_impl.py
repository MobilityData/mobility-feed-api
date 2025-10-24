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

from feeds_gen.models.source_info import SourceInfo
from feeds_gen.models.update_request_gtfs_rt_feed import (
    UpdateRequestGtfsRtFeed,
)
from feeds_operations.impl.models.operation_entity_type_impl import (
    OperationEntityTypeImpl,
)
from feeds_operations.impl.models.operation_external_id_impl import (
    OperationExternalIdImpl,
)
from feeds_operations.impl.models.operation_redirect_impl import OperationRedirectImpl
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsrealtimefeed
from shared.db_models.external_id_impl import ExternalIdImpl
from shared.db_models.redirect_impl import RedirectImpl


class UpdateRequestGtfsRtFeedImpl(UpdateRequestGtfsRtFeed):
    """Implementation of the UpdateRequestGtfsRtFeed model.
    This class converts a SQLAlchemy row DB object with the gtfs feed fields to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    @classmethod
    def from_orm(cls, obj: Gtfsrealtimefeed | None) -> UpdateRequestGtfsRtFeed | None:
        """
        Convert a SQLAlchemy row object to a Pydantic model.
        """
        if obj is None:
            return None
        return cls(
            id=obj.stable_id,
            status=obj.status,
            provider=obj.provider,
            feed_name=obj.feed_name,
            note=obj.note,
            feed_contact_email=obj.feed_contact_email,
            source_info=SourceInfo(
                producer_url=obj.producer_url,
                authentication_type=None
                if obj.authentication_type is None
                else int(obj.authentication_type),
                authentication_info_url=obj.authentication_info_url,
                api_key_parameter_name=obj.api_key_parameter_name,
                license_url=obj.license_url,
            ),
            redirects=sorted(
                [RedirectImpl.from_orm(item) for item in obj.redirectingids],
                key=lambda x: x.target_id,
            ),
            external_ids=sorted(
                [ExternalIdImpl.from_orm(item) for item in obj.externalids],
                key=lambda x: x.external_id,
            ),
            entity_types=sorted(
                [OperationEntityTypeImpl.from_orm(item) for item in obj.entitytypes]
                if obj.entitytypes
                else []
            ),
            feed_references=sorted([item.stable_id for item in obj.gtfs_feeds]),
            official=obj.official,
        )

    @classmethod
    def to_orm(
        cls, update_request: UpdateRequestGtfsRtFeed, entity: Gtfsrealtimefeed, session
    ) -> Gtfsrealtimefeed:
        """
        Convert a Pydantic model to a SQLAlchemy row object.
        """
        entity.status = update_request.status
        entity.provider = update_request.provider
        entity.feed_name = update_request.feed_name
        entity.note = update_request.note
        entity.feed_contact_email = update_request.feed_contact_email
        entity.official = update_request.official
        entity.producer_url = (
            None
            if (
                update_request.source_info is None
                or update_request.source_info.producer_url is None
            )
            else update_request.source_info.producer_url
        )
        entity.authentication_type = (
            None
            if (
                update_request.source_info is None
                or update_request.source_info.authentication_type is None
            )
            else str(update_request.source_info.authentication_type)
        )
        entity.authentication_info_url = (
            None
            if (
                update_request.source_info is None
                or update_request.source_info.authentication_info_url is None
            )
            else update_request.source_info.authentication_info_url
        )
        entity.api_key_parameter_name = (
            None
            if (
                update_request.source_info is None
                or update_request.source_info.api_key_parameter_name is None
            )
            else update_request.source_info.api_key_parameter_name
        )
        entity.license_url = (
            None
            if (
                update_request.source_info is None
                or update_request.source_info.license_url is None
            )
            else update_request.source_info.license_url
        )

        redirecting_ids = (
            []
            if update_request.redirects is None
            else [
                OperationRedirectImpl.to_orm(item, entity, session)
                for item in update_request.redirects
            ]
        )
        entity.redirectingids.clear()
        entity.redirectingids.extend(redirecting_ids)

        entity.externalids = (
            []
            if update_request.external_ids is None
            else [
                OperationExternalIdImpl.to_orm(item, entity)
                for item in update_request.external_ids
            ]
        )
        entity.entitytypes = (
            []
            if update_request.entity_types is None
            else [
                OperationEntityTypeImpl.to_orm(item, session)
                for item in update_request.entity_types
            ]
        )
        entity.gtfs_feeds = (
            []
            if update_request.feed_references is None
            else [
                session.query(Gtfsfeed).filter(Gtfsfeed.stable_id == item).one()
                for item in update_request.feed_references
            ]
        )
        return entity
