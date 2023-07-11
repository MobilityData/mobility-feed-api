# coding: utf-8

from __future__ import annotations
from datetime import date, datetime  # noqa: F401

import re  # noqa: F401
from typing import Any, Dict, List, Optional  # noqa: F401

from pydantic import AnyUrl, BaseModel, EmailStr, Field, validator  # noqa: F401


class DatasetId(BaseModel):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.

    DatasetId - a model defined in OpenAPI

        id: The id of this DatasetId [Optional].
    """

    id: Optional[str] = Field(alias="id", default=None)

DatasetId.update_forward_refs()
