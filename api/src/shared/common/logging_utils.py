import logging
import os


def get_env_logging_level():
    """
    Get the logging level from the environment via OS variable LOGGING_LEVEL. Returns INFO if not set.
    """
    return logging.getLevelName(os.getenv("LOGGING_LEVEL", "INFO"))


class Logger:
    """
    Util class for logging information, errors or warnings
    """

    def __init__(self, name):
        """
        Initialize the logger
        """
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        self.logger = logging.getLogger(name)
        self.logger.addHandler(console_handler)
        self.logger.setLevel(get_env_logging_level())

    def get_logger(self):
        """
        Get the logger instance
        :return: the logger instance
        """
        return self.logger
