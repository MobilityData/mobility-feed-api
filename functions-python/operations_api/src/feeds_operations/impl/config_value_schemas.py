#
#   MobilityData 2026
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
"""JSON Schemas a per-feed config override must match, keyed by (namespace, key).

A config key does nothing until code reads it, so the shape of its values is defined
here, next to the code, when the key is registered by its migration. A registered key
without an entry accepts any JSON value.
"""

from typing import Any, Dict, Final, Optional, Tuple

# RFC 9110 field-name token.
_HEADER_NAME_PATTERN: Final = r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$"

# Credential headers are refused: values are stored in plain text, and a feed's API key
# is applied at download time from the FEEDS_CREDENTIALS secret. Spelled case by case
# because JSON Schema patterns have no case-insensitive flag.
_CREDENTIAL_HEADERS: Final = (
    "Authorization",
    "Proxy-Authorization",
    "Cookie",
    "X-Api-Key",
)


def _any_case(word: str) -> str:
    return "".join(f"[{c.upper()}{c.lower()}]" if c.isalpha() else c for c in word)


_CREDENTIAL_HEADER_PATTERN: Final = (
    "^(" + "|".join(_any_case(h) for h in _CREDENTIAL_HEADERS) + ")$"
)

_PARQUET_SIZES: Final = ["s", "m", "l"]

VALUE_SCHEMAS: Final[Dict[Tuple[str, str], Dict[str, Any]]] = {
    # Read by helpers/utils.py build_feed_request_params; replaces the default headers.
    ("feed_download", "http_headers"): {
        "type": "object",
        "maxProperties": 50,
        "propertyNames": {
            "pattern": _HEADER_NAME_PATTERN,
            "not": {"pattern": _CREDENTIAL_HEADER_PATTERN},
        },
        "additionalProperties": {"type": "string", "pattern": r"^[^\r\n]*$"},
    },
    # Read by helpers/sizing.py: a bare size, or the size with who set it and a lock.
    ("parquet_builder", "size"): {
        "oneOf": [
            {"type": "string", "enum": _PARQUET_SIZES},
            {
                "type": "object",
                "required": ["size"],
                "properties": {
                    "size": {"type": "string", "enum": _PARQUET_SIZES},
                    "source": {"type": "string"},
                    "locked": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        ]
    },
}


def value_schema(namespace: str, key: str) -> Optional[Dict[str, Any]]:
    return VALUE_SCHEMAS.get((namespace, key))
