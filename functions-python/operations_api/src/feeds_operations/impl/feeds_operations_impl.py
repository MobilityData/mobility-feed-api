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
from typing import Annotated

from deepdiff import DeepDiff
from fastapi import HTTPException
from pydantic import Field
from starlette.responses import Response

from database_gen.sqlacodegen_models import Gtfsfeed, t_feedsearch
from feeds_operations.impl.models.update_request_gtfs_feed_impl import (
    UpdateRequestGtfsFeedImpl,
)
from feeds_operations_gen.apis.operations_api_base import BaseOperationsApi
from feeds_operations_gen.models.data_type import DataType
from feeds_operations_gen.models.update_request_gtfs_feed import UpdateRequestGtfsFeed
from feeds_operations_gen.models.update_request_gtfs_rt_feed import (
    UpdateRequestGtfsRtFeed,
)
from helpers.database import start_db_session, refresh_materialized_view
from helpers.query_helper import query_feed_by_stable_id
from .models.update_request_gtfs_rt_feed_impl import UpdateRequestGtfsRtFeedImpl
from .request_validator import validate_request

logging.basicConfig(level=logging.INFO)


class OperationsApiImpl(BaseOperationsApi):
    """
    Implementation of the operations API
    """

    @staticmethod
    def detect_changes(
        feed: Gtfsfeed,
        update_request_feed: UpdateRequestGtfsFeed | UpdateRequestGtfsRtFeed,
        impl_class: UpdateRequestGtfsFeedImpl | UpdateRequestGtfsRtFeedImpl,
    ) -> DeepDiff:
        """
        Detect changes between the feed and the update request.
        """
        # Normalize the feed and the update request and compare them
        copy_feed = impl_class.from_orm(feed)
        # Temporary solution to update the operational status
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
                f"Detect update changes: affected paths: {diff.affected_paths}"
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
        ...
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
        session = None
        try:
            session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
            feed: Gtfsfeed = query_feed_by_stable_id(
                session, update_request_feed.id, data_type.value
            )
            if feed is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Feed ID not found: {update_request_feed.id}",
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
                impl_class.to_orm(update_request_feed, feed, session)
                # This is a temporary solution as the operational_status is not visible in the diff
                feed.operational_status = (
                    feed.operational_status
                    if update_request_feed.operational_status_action == "no_change"
                    else update_request_feed.operational_status_action
                )
                session.add(feed)
                refreshed = refresh_materialized_view(session, t_feedsearch.name, False)
                logging.info(
                    f"Materialized view {t_feedsearch.name} refreshed: {refreshed}"
                )
                session.commit()
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
        finally:
            if session:
                session.close()
