import logging
import os
import threading

from google.cloud.logging.handlers import CloudLoggingHandler
import google.cloud.logging
from google.cloud.logging_v2 import Client

from middleware.request_context import get_request_context
from utils.config import get_config, PROJECT_ID


def get_env_logging_level():
    """
    Get the logging level from the environment via OS variable LOGGING_LEVEL. Returns INFO if not set.
    """
    return os.getenv("LOGGING_LEVEL", "INFO")


def is_local_env():
    return os.getenv("K_SERVICE") is None

lock = threading.Lock()
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
        with lock:
            if hasattr(Logger, "initialized"):
                return
            logging.basicConfig(level=get_env_logging_level())
            if is_local_env():
                # Use the default logging handler
                logging.info("Using default logging handler")
                return
            try:
                client = google.cloud.logging_v2.Client()
                client.get_default_handler()
                client.setup_logging()
                logging.info("GCP logging client initialized")
            except Exception as error:
                # This might happen when the GCP authorization credentials are not available.
                # Example, when running the tests locally
                logging.error(f"Error initializing the logger: {error}")
        Logger.initialized = True

    def get_logger(self):
        return self.logger


class TraceLogger:
    def __init__(self, logger: logging.Logger, project_id: str, trace_id: str, span_id: str):
        self._logger = logger
        self._trace_id = None
        self._span_id = None
        self._project_id = project_id
        self._trace_id = trace_id
        self._span_id = span_id

    def _inject_trace(self, extra):
        if not self._trace_id or not self._span_id:
            return extra or {}

        trace_fields = {
            "logging.googleapis.com/trace": f"projects/{self._project_id}/traces/{self._trace_id}",
            "logging.googleapis.com/spanId": self._span_id,
            "logging.googleapis.com/trace_sampled": True,
        }
        if extra:
            trace_fields.update(extra)
        return trace_fields

    def info(self, msg, *args, extra=None, **kwargs):
        return self._logger.info(msg, *args, extra=self._inject_trace(extra), **kwargs)

    def error(self, msg, *args, extra=None, **kwargs):
        return self._logger.error(msg, *args, extra=self._inject_trace(extra), **kwargs)

    def warning(self, msg, *args, extra=None, **kwargs):
        return self._logger.warning(msg, *args, extra=self._inject_trace(extra), **kwargs)

    def debug(self, msg, *args, extra=None, **kwargs):
        return self._logger.debug(msg, *args, extra=self._inject_trace(extra), **kwargs)

    def exception(self, msg, *args, extra=None, **kwargs):
        return self._logger.exception(msg, *args, extra=self._inject_trace(extra), **kwargs)


def new_logger(name: str):
    """
    Create a new logger with the given name.
    """
    logger = logging.getLogger(name)
    logger.setLevel(get_env_logging_level())
    if not logger.handlers:
        if is_local_env():
            handler = logging.StreamHandler()
        else:
            from google.cloud.logging import Client
            from google.cloud.logging.handlers import CloudLoggingHandler
            client = Client()
            handler = CloudLoggingHandler(client)

        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        request_context = get_request_context()
        if not request_context:
            return logger
        return TraceLogger(logger, get_config(PROJECT_ID), request_context.get("trace_id"), request_context.get("span_id"))


