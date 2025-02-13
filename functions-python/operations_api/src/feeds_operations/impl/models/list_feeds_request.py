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

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class DataType(str, Enum):
    """Enumeration for feed data types."""

    GTFS = "gtfs"
    GTFS_RT = "gtfs_rt"


class OperationalStatus(str, Enum):
    """Enumeration for feed operational status."""

    WIP = "wip"
    PUBLISHED = "published"


class ListFeedsRequest(BaseModel):
    """Request model for listing feeds with filtering and pagination."""

    operation_status: Optional[OperationalStatus] = Field(
        None, description="Filter feeds by operational status (wip or published)"
    )

    data_type: Optional[DataType] = Field(
        None, description="Filter feeds by data type (gtfs or gtfs_rt)"
    )

    offset: int = Field(
        default=0, ge=0, description="Number of items to skip for pagination"
    )

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to return (1-100)",
    )

    class Config:
        use_enum_values = True
        from_attributes = True
