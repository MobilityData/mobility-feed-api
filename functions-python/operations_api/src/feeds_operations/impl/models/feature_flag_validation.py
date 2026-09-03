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

from fastapi import HTTPException

# Maps a flag's value_type to the JSON/Python type(s) its value must have.
VALUE_TYPE_LABELS = {
    "boolean": "a boolean",
    "string": "a string",
    "numeric": "a number",
    "array": "an array",
    "json": "an object",
}


def validate_value_type(value_type: str, value) -> None:
    """Ensures `value` is compatible with the declared `value_type`.

    Raises HTTPException(422) when the value's shape does not match the type.
    """
    if value_type == "boolean":
        ok = isinstance(value, bool)
    elif value_type == "string":
        ok = isinstance(value, str)
    elif value_type == "numeric":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif value_type == "array":
        ok = isinstance(value, list)
    elif value_type == "json":
        ok = isinstance(value, dict)
    else:
        ok = False

    if not ok:
        raise HTTPException(
            status_code=422,
            detail=(
                f"default_value does not match value_type '{value_type}': "
                f"expected {VALUE_TYPE_LABELS.get(value_type, 'a valid value')}."
            ),
        )
