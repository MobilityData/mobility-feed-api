# coding: utf-8

from __future__ import annotations
from datetime import date, datetime  # noqa: F401

import re  # noqa: F401
from typing import Any, Dict, List, Optional  # noqa: F401

from pydantic import AnyUrl, BaseModel, EmailStr, Field, validator  # noqa: F401
from feeds_gen.models.data_type import DataType
from feeds_gen.models.feed_status import FeedStatus


class BasicFeed(BaseModel):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.

    BasicFeed - a model defined in OpenAPI

        id: The id of this BasicFeed [Optional].
        data_type: The data_type of this BasicFeed [Optional].
        status: The status of this BasicFeed [Optional].
        provider: The provider of this BasicFeed [Optional].
        feed_name: The feed_name of this BasicFeed [Optional].
        note: The note of this BasicFeed [Optional].
    """

    id: Optional[str] = Field(alias="id", default=None)
    data_type: Optional[DataType] = Field(alias="data_type", default=None)
    status: Optional[FeedStatus] = Field(alias="status", default=None)
    provider: Optional[str] = Field(alias="provider", default=None)
    feed_name: Optional[str] = Field(alias="feed_name", default=None)
    note: Optional[str] = Field(alias="note", default=None)

BasicFeed.update_forward_refs()
