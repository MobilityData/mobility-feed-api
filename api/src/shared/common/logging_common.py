import os


def get_env_logging_level():
    """
    Get the logging level from the environment via OS variable LOGGING_LEVEL. Returns INFO if not set.
    """
    return os.getenv("LOGGING_LEVEL", "INFO")