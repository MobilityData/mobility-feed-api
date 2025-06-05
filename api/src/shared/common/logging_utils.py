import logging
import os


def get_env_logging_level():
    """
    Get the logging level from the environment via OS variable LOGGING_LEVEL. Returns INFO if not set.
    """
    return logging.getLevelName(os.getenv("LOGGING_LEVEL", "INFO"))
