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

from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl


class BoundingFilterMethod(str, Enum):
    """Enum for bounding box filtering methods."""
    COMPLETELY_ENCLOSED = "completely_enclosed"
    PARTIALLY_ENCLOSED = "partially_enclosed"
    DISJOINT = "disjoint"


class ListFeedsRequest(BaseModel):
    """Base request model for listing feeds."""
    operation_status: Optional[str] = Field(
        None,
        description="Filter feeds by operational status",
        enum=["wip", "published"]
    )
    provider: Optional[str] = Field(
        None,
        description="List only feeds with the specified provider. Can be a partial match. Case insensitive."
    )
    producer_url: Optional[HttpUrl] = Field(
        None,
        description="List only feeds with the specified producer URL. Can be a partial match. Case insensitive."
    )
    country_code: Optional[str] = Field(
        None,
        description="Filter feeds by their exact country code."
    )
    subdivision_name: Optional[str] = Field(
        None,
        description="List only feeds with the specified subdivision name. Can be a partial match. Case insensitive."
    )
    municipality: Optional[str] = Field(
        None,
        description="List only feeds with the specified municipality. Can be a partial match. Case insensitive."
    )
    is_official: Optional[bool] = Field(
        False,
        description="If true, only return official feeds."
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of items to skip for pagination"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to return"
    )


class ListGtfsFeedsRequest(ListFeedsRequest):
    """Request model for listing GTFS feeds."""
    dataset_latitudes: Optional[str] = Field(
        None,
        description="Specify the minimum and maximum latitudes of the bounding box to use for filtering."
    )
    dataset_longitudes: Optional[str] = Field(
        None,
        description="Specify the minimum and maximum longitudes of the bounding box to use for filtering."
    )
    bounding_filter_method: Optional[BoundingFilterMethod] = Field(
        BoundingFilterMethod.COMPLETELY_ENCLOSED,
        description="Specify the filtering method to use with the dataset_latitudes and dataset_longitudes parameters."
    )


class ListGtfsRtFeedsRequest(ListFeedsRequest):
    """Request model for listing GTFS-RT feeds."""
    entity_types: Optional[str] = Field(
        None,
        description="Filter feeds by their entity type. Expects a comma separated list of all types to fetch."
    )
