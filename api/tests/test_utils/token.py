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

import jwt
from api.tests.test_utils.cryptography import private_key, public_key
from jwt.utils import to_base64url_uint

ALGORITHM = "RS256"
PUBLIC_KEY_ID = "test-public-key-id"


def encode_token(payload):
    """Encode a JWT token"""
    return jwt.encode(
        payload=payload,
        key=private_key,
        algorithm=ALGORITHM,
        headers={
            "kid": PUBLIC_KEY_ID,
        },
    )


def get_mock_user_claims(permissions):
    """Get a mock user claims dictionary"""
    return {
        "sub": "test|auth0",
        "iss": "test-issuer",
        "aud": "audience",
        "iat": 0,  # 1/1/1970
        "exp": 9999999999,  # 11/20/2286
        "permissions": permissions,
    }


def get_mock_token(permissions):
    """Get a mock JWT token"""
    return encode_token(get_mock_user_claims(permissions))


def get_mock_read_only_token():
    """Get a mock read-only JWT token"""
    return get_mock_token(permissions=["read"])


def get_mock_read_write_token():
    """Get a mock read-write JWT token"""
    return get_mock_token(permissions=["read", "write"])


def get_jwk(pb_key):
    """Get a JWK from a public key"""
    public_numbers = pb_key.public_numbers()

    return {
        "kid": PUBLIC_KEY_ID,  # Public key id constant from previous step
        "alg": ALGORITHM,  # Algorithm constant from previous step
        "kty": "RSA",
        "use": "sig",
        "n": to_base64url_uint(public_numbers.n).decode("ascii"),
        "e": to_base64url_uint(public_numbers.e).decode("ascii"),
    }


jwk = get_jwk(public_key)

authHeaders = {"Authorization": f"Bearer {jwk}"}
