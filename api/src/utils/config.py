import os
from typing import Final

PROJECT_ID: Final[str] = "PROJECT_ID"


def get_config(key: str, default_value: str = None) -> str:
    """
    Get the value of an environment variable
    """
    return os.getenv(key, default_value)
