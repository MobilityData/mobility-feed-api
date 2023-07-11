# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from feeds_gen.models.metadata import Metadata
from feeds_gen.security_api import get_token_ApiKeyAuth

class BaseMetadataApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseMetadataApi.subclasses = BaseMetadataApi.subclasses + (cls,)
    def metadata_get(
        self,
    ) -> Metadata:
        """Get metadata about this API."""
        ...
