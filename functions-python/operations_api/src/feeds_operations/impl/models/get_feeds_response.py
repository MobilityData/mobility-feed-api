# coding: utf-8

"""
    Mobility Database Catalog Operations

    API for the Mobility Database Catalog Operations. See [https://mobilitydatabase.org/]
    (https://mobilitydatabase.org/).  This API was designed for internal use and is not intended to be used by
    the general public. The Mobility Database Operation API uses Auth2.0 authentication.

    The version of the OpenAPI document: 1.0.0
    Contact: api@mobilitydata.org
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""

from __future__ import annotations

import json
import pprint
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, StrictInt

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

from feeds_operations_gen.models.base_feed import BaseFeed


class GetFeeds200Response(BaseModel):
    """Response model for get_feeds endpoint"""

    total: Optional[StrictInt] = Field(
        default=None, description="Total number of feeds matching the criteria."
    )
    offset: Optional[StrictInt] = Field(
        default=None, description="Current offset for pagination."
    )
    limit: Optional[StrictInt] = Field(
        default=None, description="Maximum number of items per page."
    )
    feeds: Optional[List[BaseFeed]] = Field(
        default=None, description="List of feeds using polymorphic serialization"
    )

    model_config = {
        "populate_by_name": True,
        "validate_assignment": True,
        "protected_namespaces": (),
    }

    def to_str(self) -> str:
        """Returns the string representation of the model using alias"""
        return pprint.pformat(self.model_dump(by_alias=True))

    def to_json(self) -> str:
        """Returns the JSON representation of the model using alias"""
        return json.dumps(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        """Return the dictionary representation of the model using alias"""
        _dict = self.model_dump(
            by_alias=True,
            exclude={},
            exclude_none=True,
        )
        if self.feeds:
            _dict["feeds"] = [feed.to_dict() for feed in self.feeds]
        return _dict

    @classmethod
    def from_dict(cls, obj: Dict) -> Self:
        """Create an instance of GetFeeds200Response from a dict"""
        if obj is None:
            return None

        if not isinstance(obj, dict):
            return cls.model_validate(obj)

        _obj = cls.model_validate(
            {
                "total": obj.get("total"),
                "offset": obj.get("offset"),
                "limit": obj.get("limit"),
                "feeds": [BaseFeed.from_dict(feed) for feed in obj.get("feeds", [])]
                if obj.get("feeds")
                else None,
            }
        )
        return _obj
