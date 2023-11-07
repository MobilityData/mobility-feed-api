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
import flask
import functions_framework
from flask import Response
import requests
from typing import Final
from datetime import datetime
from datetime import timezone

IDP_TOKEN_URL: Final[str] = 'https://securetoken.googleapis.com/v1/token'
HEADERS: Final[dict[str, str]] = {
    'Content-Type': 'application/json',
    'user-agent': 'MobilityDataCatalog',
}
gcp_idp_api_key = os.environ.get('GCP_IDP_API_KEY')


class TokenPostResponse:
    def __init__(self, access_token: str, expiration_datetime_utc: str, token_type: str):
        self.access_token = access_token
        self.expiration_datetime_utc = expiration_datetime_utc
        self.token_type = token_type


class TokenPostResponseError:
    def __init__(self, error: str):
        self.error = error


def get_idp_response(refresh_token: str) -> requests.Response:
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'audiences': 'feed_api',
    }
    idp_response = requests.post(IDP_TOKEN_URL + f'?key={gcp_idp_api_key}', headers=HEADERS, data=json.dumps(data))
    return idp_response


def create_response_from_idp(idp_response):
    response_data = idp_response.json()
    access_token = response_data.get('access_token')
    token_content = jwt.decode(access_token, options={"verify_signature": False}, algorithms=['RS256'])
    expiration_datetime_utc = datetime.fromtimestamp(token_content.get('exp'), timezone.utc).isoformat().replace(
        '+00:00', 'Z')
    token_post_response = TokenPostResponse(access_token, expiration_datetime_utc, response_data.get('token_type'))
    return Response(status=200, mimetype="application/json", headers={},
                    response=json.dumps(token_post_response.__dict__))


@functions_framework.http
def tokens_post(request: flask.Request) -> Response:
    """
    This function is triggered by a POST request to /tokens
    only support POST requests and the request body must contain a refresh_token
    :param request: HTTP request
    """
    if request.method != 'POST':
        return Response(status=405, mimetype="application/json", headers={},
                        response=json.dumps(TokenPostResponseError('Invalid request method.').__dict__))

    if not request.get_json() or 'refresh_token' not in request.get_json():
        return Response(status=400, mimetype="application/json", headers={},
                        response=json.dumps(TokenPostResponseError('Bad Request.').__dict__))

    idp_response = get_idp_response(request.get_json().get('refresh_token'))

    if idp_response.status_code != 200:
        print(f'Error retrieving refresh token : {idp_response.json()}')
        return Response(status=500, mimetype="application/json", headers={},
                        response=json.dumps(TokenPostResponseError('Error generating access token.').__dict__))
    try:
        return create_response_from_idp(idp_response)
    except Exception as e:
        print(f'Error creating response from idp : {e}')
        return Response(status=500, mimetype="application/json", headers={},
                        response=json.dumps(TokenPostResponseError('Error generating access token.').__dict__))
