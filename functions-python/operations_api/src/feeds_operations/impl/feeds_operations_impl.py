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
from feeds_operations.impl.models.get_feeds_response import GetFeeds200Response
from feeds_operations.impl.models.gtfs_feed_impl import GtfsFeedImpl
from feeds_operations.impl.models.gtfs_rt_feed_impl import GtfsRtFeedImpl
from feeds_operations.impl.models.update_request_gtfs_feed_impl import (
    UpdateRequestGtfsFeedImpl,
)
from feeds_operations.impl.models.update_request_gtfs_rt_feed_impl import (
    UpdateRequestGtfsRtFeedImpl,
)
from feeds_operations_gen.apis.operations_api_base import BaseOperationsApi
from feeds_operations_gen.models.data_type import DataType
from feeds_operations_gen.models.gtfs_feed_response import GtfsFeedResponse
from feeds_operations_gen.models.gtfs_rt_feed_response import GtfsRtFeedResponse
from feeds_operations_gen.models.update_request_gtfs_feed import UpdateRequestGtfsFeed
from feeds_operations_gen.models.update_request_gtfs_rt_feed import (
    UpdateRequestGtfsRtFeed,
)
from pydantic import Field
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    t_feedsearch,
)
from shared.helpers.database import Database, refresh_materialized_view
from shared.helpers.query_helper import (
    query_feed_by_stable_id,
    get_feeds_query,
    get_eager_loading_options,
    get_model,
)
from starlette.responses import Response
from .request_validator import validate_request

logging.basicConfig(level=logging.INFO)


class OperationsApiImpl(BaseOperationsApi):
    """Implementation of the operations API."""

    def process_feed(self, feed) -> GtfsFeedResponse | GtfsRtFeedResponse | None:
        """Process a feed into the appropriate response type using fromOrm methods."""
        if not feed:
            logging.error("Received None feed object")
            return None

        if not hasattr(feed, "data_type") or not feed.data_type:
            logging.error(
                f"Feed {feed.stable_id if hasattr(feed, 'stable_id') else 'unknown'} missing data_type"
            )
            return None

        try:
            logging.info(f"Processing feed {feed.stable_id} with type {feed.data_type}")

            if feed.data_type == "gtfs":
                result = GtfsFeedImpl.from_orm(feed)
                logging.info(f"Successfully processed GTFS feed {feed.stable_id}")
                return result
            elif feed.data_type == "gtfs_rt":
                result = GtfsRtFeedImpl.from_orm(feed)
                logging.info(f"Successfully processed GTFS-RT feed {feed.stable_id}")
                return result
            else:
                logging.error(f"Unknown feed type: {feed.data_type}")
                return None

        except Exception as e:
            logging.error(
                f"Error processing feed {feed.stable_id if hasattr(feed, 'stable_id') else 'unknown'}: {str(e)}"
            )
            return None

    async def get_feeds(
        self,
        operation_status: Optional[str] = None,
        data_type: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> GetFeeds200Response:
        """Get a list of feeds with optional filtering and pagination."""
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

                feed_list = []
                for feed in feeds:
                    try:
                        if feed is None:
                            logging.warning("Encountered None feed in results")
                            continue
                        processed_feed = self.process_feed(feed)
                        if processed_feed is not None:
                            feed_list.append(processed_feed)
                        else:
                            logging.warning(
                                f"process_feed returned None for feed {feed.stable_id if feed else 'unknown'}"
                            )
                    except Exception as e:
                        logging.error(f"Error processing feed: {str(e)}")
                        continue

                logging.info("Successfully processed %d feeds", len(feed_list))

                if not feed_list and total > 0:
                    logging.error(
                        "No feeds were successfully processed despite having results"
                    )
                    raise ValueError("Failed to process any feeds from the database")

                response = GetFeeds200Response(
                    total=total, offset=offset, limit=limit, feeds=feed_list
                )
                logging.info("Returning response with %d feeds", len(feed_list))
                return response

        except Exception as e:
            logging.error("Failed to get feeds. Error: %s", str(e))
            raise HTTPException(
                status_code=500, detail=f"Internal server error: {str(e)}"
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
        model = get_model(data_type.value)

        feed = query_feed_by_stable_id(session, update_request_feed.id, data_type.value)

        if feed is None:
            raise HTTPException(
                status_code=400,
                detail=f"Feed ID not found: {update_request_feed.id}",
            )

        eager_loading_options = get_eager_loading_options(model)
        feed = (
            session.query(model)
            .options(*eager_loading_options)
            .filter(model.id == feed.id)
            .first()
        )

        if feed is None:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve feed with eagerly loaded relationships: {update_request_feed.id}",
            )

        return feed
