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
import logging
from typing import List, Optional


def to_boolean(value, default_value: Optional[bool] = False) -> bool:
    """
    Convert a value to a boolean.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ["true", "1", "yes", "y"]
    return default_value


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
        Optional[any]: The value if found and valid, otherwise None. The str values are trimmed.
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


def to_enum(value, enum_class=None, default_value=None):
    """
    Convert a value to an enum member of the specified enum class.

    Args:
        value: The value to convert.
        enum_class: The enum class to convert the value to.
        default_value: The default value to return if conversion fails.

    Returns:
        An enum member if conversion is successful, otherwise the default value.
    """
    if enum_class and isinstance(value, enum_class):
        return value
    try:
        return enum_class(str(value))
    except (ValueError, TypeError) as e:
        logging.warning("Failed to convert value to enum member: %s", e)
        return default_value


def to_float(value, default_value: Optional[float] = None) -> Optional[float]:
    """
    Convert a value to a float. If conversion fails, return the default value.
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default_value


def get_safe_value_from_csv(
    row, column_name, default_value: str = None
) -> Optional[str]:
    """
    Get a safe value from a csv row. If the value is missing or empty, return the default value.
    """

    raw_value = row.get(column_name, None)

    return get_safe_value(raw_value, default_value)


def get_safe_value(raw_value, default_value: str = None) -> Optional[str]:
    """
    Get a safe value. If the value is missing or empty, return the default value.
    """
    import pandas

    if (
        raw_value is None
        or pandas.isna(raw_value)
        or (isinstance(raw_value, str) and raw_value.strip() == "")
    ):
        return default_value
    return f"{raw_value}".strip()


def get_safe_float_from_csv(
    row, column_name, default_value: float = None
) -> Optional[float]:
    """
    Get a safe float value from a csv row.
    Use the default value if the value is missing or cannot be converted to float.
    """
    raw_value = row.get(column_name, None)

    return get_safe_float(raw_value, default_value)


def get_safe_float(raw_value, default_value: float = None) -> Optional[float]:
    """
    Get a safe float value. Use the default value if the value is missing or cannot be converted to float.
    """
    safe_value = get_safe_value(raw_value, default_value)
    try:
        return float(safe_value)
    except (ValueError, TypeError):
        return default_value


def get_safe_int_from_csv(row, column_name, default_value: int = None) -> Optional[int]:
    """
    Get a safe int value from a csv row. Use the default value if the value is missing or cannot be converted to int.
    """
    raw_value = row.get(column_name, None)

    return get_safe_int(raw_value, default_value)


def get_safe_int(raw_value, default_value: int = None) -> Optional[int]:
    """
    Get a safe int value. Use the default value if the value is missing or cannot be converted to int.
    """
    safe_value = get_safe_value(raw_value, default_value)
    try:
        return int(safe_value)
    except (ValueError, TypeError):
        return default_value


def sanitize_value(value):
    """
    Sanitize a value by applying get_safe_value to all string fields in a nested structure.
    """
    if not value:
        return value
    if isinstance(value, str):
        return get_safe_value(value)
    if isinstance(value, dict):
        return {k: sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value(i) for i in value]
    return value
