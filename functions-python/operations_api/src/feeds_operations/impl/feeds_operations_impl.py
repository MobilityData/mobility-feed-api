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

from fastapi import HTTPException
from pydantic import Field
from starlette.responses import Response

from database_gen.sqlacodegen_models import Gtfsfeed
from feeds_operations.impl.models.update_request_gtfs_feed_impl import (
    UpdateRequestGtfsFeedImpl,
)
from .request_validator import validate_request
from feeds_operations_gen.apis.operations_api_base import BaseOperationsApi
from feeds_operations_gen.models.data_type import DataType
from feeds_operations_gen.models.update_request_gtfs_feed import UpdateRequestGtfsFeed
from helpers.database import start_db_session
from helpers.query_helper import query_feed_by_stable_id
from deepdiff import DeepDiff

logging.basicConfig(level=logging.INFO)


class OperationsApiImpl(BaseOperationsApi):
    """
    Implementation of the operations API
    """

    @staticmethod
    def detect_changes(
        feed: Gtfsfeed, update_request_gtfs_feed: UpdateRequestGtfsFeed
    ) -> DeepDiff:
        """
        Detect changes between the feed and the update request.
        """
        # Normalize the feed and the update request and compare them
        copy_feed = UpdateRequestGtfsFeedImpl.from_orm(feed)
        # Temporary solution to update the operational status
        copy_feed.operational_status_action = (
            update_request_gtfs_feed.operational_status_action
        )
        diff = DeepDiff(
            copy_feed.model_dump(),
            update_request_gtfs_feed.model_dump(),
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
        session = None
        try:
            session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
            feed: Gtfsfeed = query_feed_by_stable_id(
                session, update_request_gtfs_feed.id, DataType.GTFS.name
            )
            if feed is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Feed ID not found: {update_request_gtfs_feed.id}",
                )

            logging.info(
                f"Feed ID: {id} attempting to update with the following request: {update_request_gtfs_feed}"
            )
            diff = self.detect_changes(feed, update_request_gtfs_feed)
            if len(diff.affected_paths) > 0 or (
                update_request_gtfs_feed.operational_status_action is not None
                and update_request_gtfs_feed.operational_status_action != "no_change"
            ):
                UpdateRequestGtfsFeedImpl.to_orm(
                    update_request_gtfs_feed, feed, session
                )
                # This is a temporary solution as the operational_status is not visible in the diff
                feed.operational_status = (
                    feed.operational_status
                    if update_request_gtfs_feed.operational_status_action == "no_change"
                    else update_request_gtfs_feed.operational_status_action
                )
                session.add(feed)
                session.commit()
                logging.info(
                    f"Feed ID: {id} updated successfully with the following changes: {diff.values()}"
                )
                return Response(status_code=200)
            else:
                logging.info(f"No changes detected for feed ID: {id}")
                return Response(status_code=204)
        except Exception as e:
            logging.error(f"Failed to update feed ID: {id}. Error: {e}")
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
        finally:
            if session:
                session.close()
