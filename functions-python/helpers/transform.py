#
#   MobilityData 2024
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
from typing import List, Optional


def to_boolean(value):
    """
    Convert a value to a boolean.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ["true", "1", "yes", "y"]
    return False


def get_nested_value(
    data: dict, keys: List[str], default_value: Optional[any] = None
) -> Optional[any]:
    """
    Retrieve the value from a nested dictionary given a list of keys.

    Args:
        data (dict): The dictionary to search.
        keys (List[str]): The list of keys representing the path to the field.
        default_value: The value to return if the field is not found.

    Returns:
        Optional[str, int, float, bool, dict]: The value if found and valid, otherwise None. The str values are trimmed.
    """
    if not keys:
        return default_value
    current_data = data
    for key in keys:
        if isinstance(current_data, dict) and key in current_data:
            current_data = current_data[key]
        else:
            return default_value
    if isinstance(current_data, str):
        result = current_data.strip()
        return result if result else default_value
    return current_data
