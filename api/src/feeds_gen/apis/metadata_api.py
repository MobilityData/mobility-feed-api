# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from feeds_gen.apis.metadata_api_base import BaseMetadataApi
import feeds.impl

from fastapi import (  # noqa: F401
    APIRouter,
    Body,
    Cookie,
    Depends,
    Form,
    Header,
    Path,
    Query,
    Response,
    Security,
    status,
)

from feeds_gen.models.extra_models import TokenModel  # noqa: F401
from feeds_gen.models.metadata import Metadata
from feeds_gen.security_api import get_token_ApiKeyAuth

router = APIRouter()

ns_pkg = feeds.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/metadata",
    responses={
        200: {"model": Metadata, "description": "Successful pull of the metadata."},
    },
    tags=["metadata"],
    response_model_by_alias=True,
)
async def metadata_get(
    token_ApiKeyAuth: TokenModel = Security(
        get_token_ApiKeyAuth
    ),
) -> Metadata:
    """Get metadata about this API."""
    return BaseMetadataApi.subclasses[0]().metadata_get()
