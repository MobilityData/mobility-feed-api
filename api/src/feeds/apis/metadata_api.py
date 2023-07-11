# coding: utf-8

from typing import Dict, List  # noqa: F401

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

from feeds.models.extra_models import TokenModel  # noqa: F401
from feeds.models.metadata import Metadata
from feeds.security_api import get_token_ApiKeyAuth

router = APIRouter()


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
    return {}
