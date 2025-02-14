# coding: utf-8
#
#   MobilityData 2025
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

from pydantic import Field, model_validator
from feeds_operations.impl.models.get_feeds_response import FeedResponse


class GtfsFeedResponse(FeedResponse):
    """GTFS feed response model."""

    data_type: str = Field(default="gtfs", description="Type of feed (must be 'gtfs')")

    @model_validator(mode="after")
    def validate_data_type(self) -> "GtfsFeedResponse":
        """Validate that data_type is 'gtfs'."""
        if self.data_type != "gtfs":
            raise ValueError("data_type must be 'gtfs'")
        return self
