# coding: utf-8

from typing import List

from fastapi import Depends, Security  # noqa: F401
from fastapi.openapi.models import OAuthFlowImplicit, OAuthFlows  # noqa: F401
from fastapi.security import (  # noqa: F401
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
    OAuth2,
    OAuth2AuthorizationCodeBearer,
    OAuth2PasswordBearer,
    SecurityScopes,
)
from fastapi.security.api_key import APIKeyCookie, APIKeyHeader, APIKeyQuery  # noqa: F401

from feeds_gen.models.extra_models import TokenModel


def get_token_ApiKeyAuth(
    
    token_api_key_query: str = Security(
        APIKeyQuery(name="key", auto_error=False)
    ),
) -> TokenModel:
    """
    Check and retrieve authentication information from api_key.

    
    
    :param token_api_key_query API key provided by [key] query
    :type token_api_key_query: str
    :return: Information attached to provided api_key or None if api_key is invalid or does not allow access to called API
    :rtype: TokenModel | None
    """

    ...

