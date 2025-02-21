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

import logging
import os
from typing import Annotated, Optional

from deepdiff import DeepDiff
from fastapi import HTTPException
from pydantic import Field
from starlette.responses import Response

from feeds_operations.impl.models.get_feeds_response import GetFeeds200Response
from feeds_operations.impl.models.update_request_gtfs_feed_impl import (
    UpdateRequestGtfsFeedImpl,
)
from feeds_operations_gen.apis.operations_api_base import BaseOperationsApi
from feeds_operations_gen.models.data_type import DataType
from feeds_operations_gen.models.gtfs_feed_response import GtfsFeedResponse
from feeds_operations_gen.models.gtfs_rt_feed_response import GtfsRtFeedResponse
from feeds_operations_gen.models.update_request_gtfs_feed import UpdateRequestGtfsFeed
from feeds_operations_gen.models.update_request_gtfs_rt_feed import (
    UpdateRequestGtfsRtFeed,
)
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    t_feedsearch,
)
from shared.helpers.database import Database, refresh_materialized_view
from shared.helpers.query_helper import query_feed_by_stable_id, get_feeds_query
from .models.update_request_gtfs_rt_feed_impl import UpdateRequestGtfsRtFeedImpl
from .request_validator import validate_request

logging.basicConfig(level=logging.INFO)


class OperationsApiImpl(BaseOperationsApi):
    """Implementation of the operations API."""

    def process_feed(self, feed) -> GtfsFeedResponse | GtfsRtFeedResponse:
        """Process a feed into the appropriate response type.

        Args:
            feed: The database feed object to process

        Returns:
            GtfsFeedResponse or GtfsRtFeedResponse depending on the feed type
        """
        if not feed:
            logging.error("Received None feed object")
            raise ValueError("Feed object cannot be None")

        try:
            common_fields = {
                "id": feed.id,
                "stable_id": feed.stable_id,
                "status": feed.status,
                "data_type": feed.data_type,
                "provider": feed.provider,
                "feed_name": feed.feed_name or "",
                "note": feed.note or "",
                "feed_contact_email": feed.feed_contact_email or "",
                "producer_url": feed.producer_url or "",
                "authentication_type": feed.authentication_type or 0,
                "authentication_info_url": feed.authentication_info_url or "",
                "api_key_parameter_name": feed.api_key_parameter_name or "",
                "license_url": feed.license_url or "",
                "operational_status": feed.operational_status,
                "created_at": str(feed.created_at) if feed.created_at else None,
                "official": feed.official if hasattr(feed, "official") else None,
                "locations": [
                    {
                        "country_code": loc.country_code,
                        "country": loc.country,
                        "subdivision_name": loc.subdivision_name,
                        "municipality": loc.municipality,
                    }
                    for loc in feed.locations
                ]
                if feed.locations
                else [],
            }

            if feed.data_type == "gtfs":
                logging.info(f"Processing GTFS feed {feed.stable_id}")
                return GtfsFeedResponse(**common_fields)
            elif feed.data_type == "gtfs_rt":
                logging.info(f"Processing GTFS-RT feed {feed.stable_id}")
                entity_types = []
                feed_references = []

                if hasattr(feed, "entitytypes") and feed.entitytypes:
                    entity_types = [et.name.lower() for et in feed.entitytypes]
                    logging.info(
                        f"Found {len(entity_types)} entity types for feed {feed.stable_id}"
                    )

                if hasattr(feed, "gtfs_feeds") and feed.gtfs_feeds:
                    feed_references = [ref.stable_id for ref in feed.gtfs_feeds]
                    logging.info(
                        f"Found {len(feed_references)} feed references for feed {feed.stable_id}"
                    )

                return GtfsRtFeedResponse(
                    **common_fields,
                    entity_types=entity_types,
                    feed_references=feed_references,
                )
            else:
                raise ValueError(f"Unknown feed type: {feed.data_type}")

        except Exception as e:
            logging.error(
                f"Error processing feed {feed.stable_id if feed else 'unknown'}: {str(e)}"
            )
            raise

    async def get_feeds(
        self,
        operation_status: Optional[str] = None,
        data_type: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> GetFeeds200Response:
        """Get a list of feeds with optional filtering and pagination.

        Args:
            operation_status: Optional filter for operational status (wip or published)
            data_type: Optional filter for feed type (gtfs or gtfs_rt)
            offset: Number of items to skip for pagination
            limit: Maximum number of items to return (default: 50)

        Returns:
            GetFeeds200Response: Contains total count, offset, limit, and list of feeds

        Raises:
            HTTPException: For database errors or invalid parameters
        """
        db = Database(database_url=os.getenv("FEEDS_DATABASE_URL"))
        try:
            with db.start_db_session() as db_session:
                query = get_feeds_query(
                    db_session=db_session,
                    operation_status=operation_status,
                    data_type=data_type,
                    limit=limit,
                    offset=offset,
                )

                logging.info("Executing query with data_type: %s", data_type)

                total = query.count()
                feeds = query.all()
                logging.info("Retrieved %d feeds from database", len(feeds))

                feed_list = [self.process_feed(feed) for feed in feeds]
                logging.info("Processed %d feeds", len(feed_list))

                response = GetFeeds200Response(
                    total=total, offset=offset, limit=limit, feeds=feed_list
                )
                logging.info("Returning response with %d feeds", len(feed_list))
                return response

        except Exception as e:
            logging.error("Failed to get feeds. Error: %s", e)
            raise HTTPException(
                status_code=500, detail="Internal server error: {}".format(e)
            )

    @staticmethod
    def detect_changes(
        feed: Gtfsfeed,
        update_request_feed: UpdateRequestGtfsFeed | UpdateRequestGtfsRtFeed,
        impl_class: UpdateRequestGtfsFeedImpl | UpdateRequestGtfsRtFeedImpl,
    ) -> DeepDiff:
        """Detect changes between the feed and the update request."""
        copy_feed = impl_class.from_orm(feed)
        copy_feed.operational_status_action = (
            update_request_feed.operational_status_action
        )
        diff = DeepDiff(
            copy_feed.model_dump(),
            update_request_feed.model_dump(),
            ignore_order=True,
        )
        if diff.affected_paths:
            logging.info(
                "Detect update changes: affected paths: %s", diff.affected_paths
            )
        else:
            logging.info("Detect update changes: no changes detected")
        return diff

    @validate_request(UpdateRequestGtfsFeed, "update_request_gtfs_feed")
    async def update_gtfs_feed(
        self,
        update_request_gtfs_feed: Annotated[
            UpdateRequestGtfsFeed,
            Field(description="Payload to update the specified feed."),
        ],
    ) -> Response:
        """Update the specified feed in the Mobility Database.
        returns:
            - 200: Feed updated successfully.
            - 204: No changes detected.
            - 400: Feed ID not found.
            - 500: Internal server error.
        """
        return await self._update_feed(update_request_gtfs_feed, DataType.GTFS)

    @validate_request(UpdateRequestGtfsRtFeed, "update_request_gtfs_rt_feed")
    async def update_gtfs_rt_feed(
        self,
        update_request_gtfs_rt_feed: Annotated[
            UpdateRequestGtfsRtFeed,
            Field(description="Payload to update the specified GTFS-RT feed."),
        ],
    ) -> Response:
        """Update the specified GTFS-RT feed in the Mobility Database.
        returns:
            - 200: Feed updated successfully.
            - 204: No changes detected.
            - 400: Feed ID not found.
            - 500: Internal server error.
        """
        return await self._update_feed(update_request_gtfs_rt_feed, DataType.GTFS_RT)

    async def _update_feed(
        self,
        update_request_feed: UpdateRequestGtfsFeed | UpdateRequestGtfsRtFeed,
        data_type: DataType,
    ) -> Response:
        """
        Update the specified feed in the Mobility Database
        """
        db = Database(database_url=os.getenv("FEEDS_DATABASE_URL"))
        try:
            with db.start_db_session() as db_session:
                feed = await OperationsApiImpl.fetch_feed(
                    data_type, db_session, update_request_feed
                )

                logging.info(
                    f"Feed ID: {update_request_feed.id} attempting to update with the following request: "
                    f"{update_request_feed}"
                )
                impl_class = (
                    UpdateRequestGtfsFeedImpl
                    if data_type == DataType.GTFS
                    else UpdateRequestGtfsRtFeedImpl
                )
                diff = self.detect_changes(feed, update_request_feed, impl_class)
                if len(diff.affected_paths) > 0 or (
                    update_request_feed.operational_status_action is not None
                    and update_request_feed.operational_status_action != "no_change"
                ):
                    await OperationsApiImpl._populate_feed_values(
                        feed, impl_class, db_session, update_request_feed
                    )
                    db_session.flush()
                    refreshed = refresh_materialized_view(db_session, t_feedsearch.name)
                    logging.info(
                        f"Materialized view {t_feedsearch.name} refreshed: {refreshed}"
                    )
                    db_session.commit()
                    logging.info(
                        f"Feed ID: {update_request_feed.id} updated successfully with the following changes: "
                        f"{diff.values()}"
                    )
                    return Response(status_code=200)
                else:
                    logging.info(
                        f"No changes detected for feed ID: {update_request_feed.id}"
                    )
                    return Response(status_code=204)
        except Exception as e:
            logging.error(
                f"Failed to update feed ID: {update_request_feed.id}. Error: {e}"
            )
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

    @staticmethod
    async def _populate_feed_values(feed, impl_class, session, update_request_feed):
        impl_class.to_orm(update_request_feed, feed, session)
        action = update_request_feed.operational_status_action
        # This is a temporary solution as the operational_status is not visible in the diff
        if action is not None and not action.lower() == "no_change":
            feed.operational_status = "wip" if action.lower() == "wip" else None
        session.add(feed)

    @staticmethod
    async def fetch_feed(data_type, session, update_request_feed):
        feed: Gtfsfeed = query_feed_by_stable_id(
            session, update_request_feed.id, data_type.value
        )
        if feed is None:
            raise HTTPException(
                status_code=400,
                detail=f"Feed ID not found: {update_request_feed.id}",
            )
        return feed
