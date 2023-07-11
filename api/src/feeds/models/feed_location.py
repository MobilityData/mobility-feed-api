# coding: utf-8

from __future__ import annotations
from datetime import date, datetime  # noqa: F401

import re  # noqa: F401
from typing import Any, Dict, List, Optional  # noqa: F401

from pydantic import AnyUrl, BaseModel, EmailStr, Field, validator  # noqa: F401
from feeds.models.bounding_box import BoundingBox


class FeedLocation(BaseModel):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.

    FeedLocation - a model defined in OpenAPI

        country_code: The country_code of this FeedLocation [Optional].
        subdivision_name: The subdivision_name of this FeedLocation [Optional].
        municipality: The municipality of this FeedLocation [Optional].
        bounding_box: The bounding_box of this FeedLocation [Optional].
    """

    country_code: Optional[str] = Field(alias="country_code", default=None)
    subdivision_name: Optional[str] = Field(alias="subdivision_name", default=None)
    municipality: Optional[str] = Field(alias="municipality", default=None)
    bounding_box: Optional[BoundingBox] = Field(alias="bounding_box", default=None)

FeedLocation.update_forward_refs()
