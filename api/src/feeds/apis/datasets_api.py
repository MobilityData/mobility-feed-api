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
from feeds.models.dataset import Dataset
from feeds.security_api import get_token_ApiKeyAuth

router = APIRouter()


@router.get(
    "/datasets/gtfs",
    responses={
        200: {"model": List[Dataset], "description": "Successful pull of the datasets info."},
    },
    tags=["datasets"],
    response_model_by_alias=True,
)
async def datasets_gtfs_get(
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
) -> List[Dataset]:
    """Get some (or all) GTFS datasets from the Mobility Database."""
    ...


@router.get(
    "/datasets/gtfs/{id}",
    responses={
        200: {"model": Dataset, "description": "Successful pull of the requested dataset."},
    },
    tags=["datasets"],
    response_model_by_alias=True,
)
async def datasets_gtfs_id_get(
    id: str = Path(description="The dataset id of the requested dataset."),
    token_ApiKeyAuth: TokenModel = Security(
        get_token_ApiKeyAuth
    ),
) -> Dataset:
    """Get the specified dataset in the Mobility Database."""
    ...


@router.get(
    "/feeds/gtfs/{id}/datasets",
    responses={
        200: {"model": List[Dataset], "description": "Successful pull of the requested datasets."},
    },
    tags=["datasets"],
    response_model_by_alias=True,
)
async def feeds_gtfs_id_datasets_get(
    id: str = Path(description="The feed id of the feed for which to obtain datasets."),
    latest: bool = Query(False, description="If true, only return the latest dataset."),
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
) -> List[Dataset]:
    """Get a list of datasets related to a feed."""
    ...
