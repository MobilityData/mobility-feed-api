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
from typing import Annotated, Optional

from deepdiff import DeepDiff
from fastapi import HTTPException
from pydantic import Field, StrictStr
from sqlalchemy.orm import Session
from starlette.responses import Response

from feeds_gen.models.data_type import DataType
from feeds_gen.models.get_feeds200_response import GetFeeds200Response
from feeds_gen.models.operation_gtfs_feed import OperationGtfsFeed
from feeds_gen.models.operation_gtfs_rt_feed import OperationGtfsRtFeed
from feeds_operations.impl.models.update_request_gtfs_feed_impl import (
    UpdateRequestGtfsFeedImpl,
)
from feeds_operations.impl.models.update_request_gtfs_rt_feed_impl import (
    UpdateRequestGtfsRtFeedImpl,
)
from feeds_gen.apis.operations_api_base import BaseOperationsApi
from feeds_gen.models.update_request_gtfs_feed import UpdateRequestGtfsFeed
from feeds_gen.models.update_request_gtfs_rt_feed import (
    UpdateRequestGtfsRtFeed,
)
from shared.database.database import with_db_session, refresh_materialized_view
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    t_feedsearch,
    Feed,
    Gtfsrealtimefeed,
)
from shared.helpers.query_helper import (
    query_feed_by_stable_id,
    get_feeds_query,
)
from .models.operation_feed_impl import OperationFeedImpl
from .models.operation_gtfs_feed_impl import OperationGtfsFeedImpl
from .models.operation_gtfs_rt_feed_impl import OperationGtfsRtFeedImpl
from .request_validator import validate_request


class OperationsApiImpl(BaseOperationsApi):
    """Implementation of the operations API."""

    @with_db_session
    async def get_feeds(
        self,
        operation_status: Optional[str] = None,
        data_type: Optional[str] = None,
        offset: str = "0",
        limit: str = "50",
        db_session: Session = None,
    ) -> GetFeeds200Response:
        """Get a list of feeds with optional filtering and pagination."""
        try:
            limit_int = int(limit) if limit else 50
            offset_int = int(offset) if offset else 0

            query = get_feeds_query(
                db_session=db_session,
                operation_status=operation_status,
                data_type=data_type,
                limit=limit_int,
                offset=offset_int,
                model=Feed,
            )

            logging.info("Executing query with data_type: %s", data_type)

            total = query.count()
            feeds = query.all()
            logging.info("Retrieved %d feeds from database", len(feeds))

            feed_list = []
            for feed in feeds:
                feed_list.append(OperationFeedImpl.from_orm(feed))

            response = GetFeeds200Response(
                total=total, offset=offset_int, limit=limit_int, feeds=feed_list
            )
            logging.info("Returning response with %d feeds", len(feed_list))
            return response

        except Exception as e:
            logging.error("Failed to get feeds. Error: %s", str(e))
            raise HTTPException(
                status_code=500, detail=f"Internal server error: {str(e)}"
            )

    @with_db_session
    async def get_gtfs_feed(
        self,
        id: Annotated[
            StrictStr, Field(description="The feed ID of the requested feed.")
        ],
        db_session: Session = None,
    ) -> OperationGtfsFeed:
        """Get the specified GTFS feed from the Mobility Database."""
        gtfs_feed = (
            db_session.query(Gtfsfeed).filter(Gtfsfeed.stable_id == id).one_or_none()
        )
        if gtfs_feed is None:
            raise HTTPException(status_code=404, detail="GTFS feed not found")
        return OperationGtfsFeedImpl.from_orm(gtfs_feed)

    @with_db_session
    async def get_gtfs_rt_feed(
        self,
        id: Annotated[
            StrictStr, Field(description="The feed ID of the requested feed.")
        ],
        db_session: Session = None,
    ) -> OperationGtfsRtFeed:
        """Get the specified GTFS-RT feed from the Mobility Database."""
        gtfs_rt_feed = (
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == id)
            .one_or_none()
        )
        if gtfs_rt_feed is None:
            raise HTTPException(status_code=404, detail="GTFS-RT feed not found")
        return OperationGtfsRtFeedImpl.from_orm(gtfs_rt_feed)

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

    @with_db_session
    async def _update_feed(
        self,
        update_request_feed: UpdateRequestGtfsFeed | UpdateRequestGtfsRtFeed,
        data_type: DataType,
        db_session: Session,
    ) -> Response:
        """
        Update the specified feed in the Mobility Database
        """
        try:
            feed_from_db = await OperationsApiImpl.fetch_feed(
                data_type, db_session, update_request_feed
            )

            logging.info(
                "Feed ID: %s attempting to update with the following request: %s",
                update_request_feed.id,
                update_request_feed,
            )
            impl_class = (
                UpdateRequestGtfsFeedImpl
                if data_type == DataType.GTFS
                else UpdateRequestGtfsRtFeedImpl
            )
            diff = self.detect_changes(feed_from_db, update_request_feed, impl_class)
            if len(diff.affected_paths) > 0 or (
                update_request_feed.operational_status_action is not None
                and update_request_feed.operational_status_action != "no_change"
            ):
                await OperationsApiImpl._populate_feed_values(
                    feed_from_db, impl_class, db_session, update_request_feed
                )
                db_session.flush()
                refreshed = refresh_materialized_view(db_session, t_feedsearch.name)
                logging.info(
                    "Materialized view %s refreshed: %s", t_feedsearch.name, refreshed
                )
                db_session.commit()
                logging.info(
                    "Feed ID: %s updated successfully with the following changes: %s",
                    update_request_feed.id,
                    diff.values(),
                )
                return Response(status_code=200)
            else:
                logging.info(
                    "No changes detected for feed ID: %s", update_request_feed.id
                )
                return Response(status_code=204)
        except Exception as e:
            logging.error(
                "Failed to update feed ID: %s. Error: %s", update_request_feed.id, e
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
            if action.lower() == "wip":
                feed.operational_status = "wip"
            elif action.lower() == "published":
                feed.operational_status = "published"
            elif action.lower() == "unpublished":
                feed.operational_status = "unpublished"
        session.add(feed)

    @staticmethod
    async def fetch_feed(data_type, session, update_request_feed):
        """Fetch a feed by its stable ID with eager loading.

        Args:
            data_type: The feed data type (gtfs or gtfs_rt)
            session: SQLAlchemy session
            update_request_feed: The update request containing the feed ID

        Returns:
            The feed object with relationships loaded

        Raises:
            HTTPException: If feed not found
        """

        feed = query_feed_by_stable_id(session, update_request_feed.id, data_type.value)

        if feed is None:
            raise HTTPException(
                status_code=400,
                detail=f"Feed ID not found: {update_request_feed.id}",
            )

        return feed
