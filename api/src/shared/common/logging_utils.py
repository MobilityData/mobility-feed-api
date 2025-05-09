import logging
import os
from google.cloud.logging.handlers import CloudLoggingHandler
import google.cloud.logging
from google.cloud.logging_v2 import Client

def get_env_logging_level():
    """
    Get the logging level from the environment via OS variable LOGGING_LEVEL. Returns INFO if not set.
    """
    return os.getenv("LOGGING_LEVEL", "INFO")


def is_local_env():
    return os.getenv("K_SERVICE") is None


class Logger:
    """
    GCP-friendly logger: structured JSON output, works locally or in production.
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        # self.logger.setLevel(get_env_logging_level())
        # self.logger.handlers.clear()

        # formatter = jsonlogger.JsonFormatter(
        #     '%(asctime)s %(levelname)s %(name)s %(message)s'
        # )
        # logging.basicConfig(level=get_env_logging_level())
        # if not is_local_env():
        #     handler = logging.StreamHandler()
        # else:
        #     try:
        #         client = google.cloud.logging.Client()
        #         client.setup_logging()
        #         # self.logger.info("GCP logging client initialized")
        #         # handler = CloudLoggingHandler(client)
        #     except Exception as e:
        #         # fallback to stdout if cloud client fails
        #         # self.logger.error(f"GCP logging failed, using fallback: {e}")
        #         handler = logging.StreamHandler()

        # handler.setFormatter(formatter)
        # self.logger.addHandler(handler)

        # Also configure SQLAlchemy to use this logger
        # self.setup_sqlalchemy_logger(handler)
        # self.logger.info("Logger initialized")

    @staticmethod
    def init_logger():
        """
        Initializes the logger
        """
        logging.basicConfig(level=get_env_logging_level())
        if is_local_env():
            # Use the default logging handler
            logging.info("Using default logging handler")
            return
        try:
            client = google.cloud.logging.Client()
            client.get_default_handler()
            client.setup_logging()
            logging.info("GCP logging client initialized")
            # return client
        except Exception as error:
            # This might happen when the GCP authorization credentials are not available.
            # Example, when running the tests locally
            logging.error(f"Error initializing the logger: {error}")
        # return None

    # def setup_sqlalchemy_logger(self, handler):
    #     sqlalchemy_loggers = [
    #         "sqlalchemy.engine",
    #         # "sqlalchemy.pool",
    #         # "sqlalchemy.dialects.postgresql",
    #         "sqlalchemy.engine.Engine",
    #     ]
    #     for logger_name in sqlalchemy_loggers:
    #         logger = logging.getLogger(logger_name)
    #         logger.setLevel(get_env_logging_level())
    #         logger.handlers.clear()
    #         logger.addHandler(handler)
    #         logger.propagate = False

    def get_logger(self):
        return self.logger

def new_logger(self, name: str):
    """
    Create a new logger with the given name.
    """
    logging.basicConfig(level=get_env_logging_level())
    return logging.getLogger(name)

