#
#   MobilityData 2023
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import json
import os
import jwt
import requests
import flask
import functions_framework
from flask import Response
from typing import Final
from datetime import datetime
from datetime import timezone
from werkzeug.exceptions import UnsupportedMediaType, BadRequest

IDP_TOKEN_URL: Final[str] = "https://securetoken.googleapis.com/v1/token"
HEADERS: Final[dict[str, str]] = {
    "Content-Type": "application/json",
    "user-agent": "MobilityDataCatalog",
}


class TokenPostResponse:
    def __init__(
            self, access_token: str, expiration_datetime_utc: str, token_type: str
    ):
        self.access_token = access_token
        self.expiration_datetime_utc = expiration_datetime_utc
        self.token_type = token_type


class TokenPostResponseError:
    """
    Error response for POST /tokens
    """

    def __init__(self, error: str):
        self.error = error


def get_idp_api_key() -> str:
    """
    Get the GCP IDP API key from the environment variables or raise an error if it is not set.
    """
    gcp_idp_api_key = os.environ.get("FEEDS_GCP_IDP_API_KEY")
    if gcp_idp_api_key is None:
        raise ValueError("FEEDS_GCP_IDP_API_KEY environment variable is not set.")
    return gcp_idp_api_key


def get_idp_response(refresh_token: str) -> requests.Response:
    """
    Get the response from the IDP API.
    Args:
        refresh_token: refresh token to be used to get the access token
    Returns: response from the IDP API
    """
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "audiences": "feed_api",
    }

    idp_response = requests.post(
        IDP_TOKEN_URL + f"?key={get_idp_api_key()}",
        headers=HEADERS,
        data=json.dumps(data),
    )
    return idp_response


def create_response_from_idp(idp_response):
    """
    Create the response from the IDP API response.
    Args:
        idp_response: response from the IDP API
    Returns:
        response to be sent to the client
    """
    response_data = idp_response.json()
    access_token = response_data.get("access_token")
    token_content = jwt.decode(
        access_token, options={"verify_signature": False}, algorithms=["RS256"]
    )
    expiration_datetime_utc = (
        datetime.fromtimestamp(token_content.get("exp"), timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    token_post_response = TokenPostResponse(
        access_token, expiration_datetime_utc, response_data.get("token_type")
    )
    return Response(
        status=200,
        mimetype="application/json",
        headers={},
        response=json.dumps(token_post_response.__dict__),
    )


def extract_refresh_token(request):
    try:
        return request.get_json().get("refresh_token")
    except UnsupportedMediaType as e:
        raise e
    except Exception as e:
        print(f"Error extracting refresh token : {e}")
        raise BadRequest()


@functions_framework.http
def tokens_post(request: flask.Request) -> Response:
    """
    This function is triggered by a POST request to /tokens
    only support POST requests and the request body must contain a refresh_token
    :param request: HTTP request
    """
    if request.method != "POST":
        return Response(
            status=405,
            mimetype="application/json",
            headers={},
            response=json.dumps(
                TokenPostResponseError("Invalid request method.").__dict__
            ),
        )

    try:
        refresh_token = extract_refresh_token(request)

        if refresh_token is None:
            return Response(
                status=400,
                mimetype="application/json",
                headers={},
                response=json.dumps(
                    TokenPostResponseError("Missing refresh_token.").__dict__
                ),
            )

        idp_response = get_idp_response(request.get_json().get("refresh_token"))

        if idp_response.status_code != 200:
            print(f"Error retrieving refresh token : {idp_response.json()}")
            return Response(
                status=500,
                mimetype="application/json",
                headers={},
                response=json.dumps(
                    TokenPostResponseError("Error generating access token.").__dict__
                ),
            )

        return create_response_from_idp(idp_response)
    except UnsupportedMediaType as e:
        print(f"Error creating response from idp : {e}")
        return Response(
            status=e.code,
            mimetype="application/json",
            headers={},
            response=json.dumps(
                TokenPostResponseError("Unsupported Media Type.").__dict__
            ),
        )
    except BadRequest as e:
        return Response(
            status=e.code,
            mimetype="application/json",
            headers={},
            response=json.dumps(TokenPostResponseError("Bad Request.").__dict__),
        )
    except Exception as e:
        print(f"Error creating response from idp : {e}")
        return Response(
            status=500,
            mimetype="application/json",
            headers={},
            response=json.dumps(
                TokenPostResponseError("Error generating access token.").__dict__
            ),
        )
