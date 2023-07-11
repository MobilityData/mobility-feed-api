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
from feeds.models.basic_feed import BasicFeed
from feeds.models.gtfs_feed import GtfsFeed
from feeds.security_api import get_token_ApiKeyAuth
from feeds.apis.feeds_api_impl import feeds_get_impl

router = APIRouter()


@router.get(
    "/feeds",
    responses={
        200: {"model": List[BasicFeed], "description": "Successful pull of the GTFS feeds info."},
    },
    tags=["feeds"],
    response_model_by_alias=True,
)
async def feeds_get(
    limit: int = Query(None, description="The number of items to be returned."),
    offset: int = Query(0, description="Offset of the first item to return.", ge=0),
    filter: str = Query(None, description="A filter to apply to the returned data. Exact syntax to be designed"),
    sort: str = Query(None, description="A specification of the sort order of the returned data. Exact syntax to be designed"),
    token_ApiKeyAuth: TokenModel = Security(
        get_token_ApiKeyAuth
    ),
) -> List[BasicFeed]:
    """Get some (or all) feeds from the Mobility Database."""
    return feeds_get_impl(limit, offset, filter, sort, token_ApiKeyAuth)


@router.get(
    "/feeds/gtfs",
    responses={
        200: {"model": List[GtfsFeed], "description": "Successful pull of the GTFS feeds info."},
    },
    tags=["feeds"],
    response_model_by_alias=True,
)
async def feeds_gtfs_get(
    limit: int = Query(None, description="The number of items to be returned."),
    offset: int = Query(0, description="Offset of the first item to return.", ge=0),
    filter: str = Query(None, description="A filter to apply to the returned data. Exact syntax to be designed"),
    sort: str = Query(None, description="A specification of the sort order of the returned data. Exact syntax to be designed"),
    bounding_latitudes: str = Query(None, description="Specify the minimum and maximum latitudes of the bounding box to use for filtering.&lt;br&gt; Must be specified alongside &#x60;boundingLongitudes&#x60;. "),
    bounding_longitudes: str = Query(None, description="Specify the minimum and maximum longitudes of the bounding box to use for filtering.&lt;br&gt; Must be specified alongside &#x60;boundingLatitudes&#x60;. "),
    bounding_filter_method: str = Query(None, description="Specify the filtering method to use with the boundingLatitudes and boundingLongitudes parameters. completely_enclosed - Get resources that are completely enclosed in the specified bounding box. partially_enclosed - Get resources that are partially enclosed in the specified bounding box. disjoint - Get resources that are completely outside the specified bounding box."),
    token_ApiKeyAuth: TokenModel = Security(
        get_token_ApiKeyAuth
    ),
) -> List[GtfsFeed]:
    """Get some (or all) GTFS feeds from the Mobility Database."""
    return []


@router.get(
    "/feeds/gtfs/{id}",
    responses={
        200: {"model": GtfsFeed, "description": "Successful pull of the requested feed."},
    },
    tags=["feeds"],
    response_model_by_alias=True,
)
async def feeds_gtfs_id_get(
    id: str = Path(description="The feed id of the requested feed."),
    token_ApiKeyAuth: TokenModel = Security(
        get_token_ApiKeyAuth
    ),
) -> GtfsFeed:
    """Get the specified feed from the Mobility Database."""
    return {}


@router.get(
    "/feeds/{id}",
    responses={
        200: {"model": BasicFeed, "description": "Successful pull of the requested feed."},
    },
    tags=["feeds"],
    response_model_by_alias=True,
)
async def feeds_id_get(
    id: str = Path(description="The feed id of the requested feed."),
    token_ApiKeyAuth: TokenModel = Security(
        get_token_ApiKeyAuth
    ),
) -> BasicFeed:
    """Get the specified feed from the Mobility Database."""
    return {}
