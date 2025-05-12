import logging
import os
import threading

from google.cloud.logging.handlers import CloudLoggingHandler
import google.cloud.logging
from google.cloud.logging_v2 import Client

from shared.common.logging_common import get_env_logging_level
from middleware.request_context import get_request_context
from utils.config import get_config, PROJECT_ID


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
            else:
                try:
                    client = google.cloud.logging_v2.Client()
                    client.get_default_handler()
                    client.setup_logging()
                    logger = _get_trace_logger(logging.getLogger("LOGGING_UTILS"))
                    logger.info("GCP logging client initialized")
                except Exception as error:
                    # This might happen when the GCP authorization credentials are not available.
                    # Example, when running the tests locally
                    logging.error(f"Error initializing the logger: {error}")
            Logger.initialized = True

    def get_logger(self):
        return self.logger


class TraceLogger:
    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._logger.propagate = True

    def _inject_trace(self, extra):
        request_context = get_request_context()
        if not request_context:
            return extra or {}
        project_id = get_config(PROJECT_ID)
        trace_id = request_context.get("trace_id")
        span_id = request_context.get("span_id")

        trace_fields = {
            "context" : {
                "trace": f"projects/{project_id}/traces/{trace_id}",
                "spanId": span_id,
                "trace_sampled": True,
            },
        }
        if extra:
            trace_fields.update(extra)
        return trace_fields

    def info(self, msg, *args, extra=None, **kwargs):
        return self._logger.info(msg, extra=self._inject_trace(extra))

    def error(self, msg, *args, extra=None, **kwargs):
        return self._logger.error(msg, *args, extra=self._inject_trace(extra), **kwargs)

    def warning(self, msg, *args, extra=None, **kwargs):
        return self._logger.warning(msg, *args, extra=self._inject_trace(extra), **kwargs)

    def debug(self, msg, *args, extra=None, **kwargs):
        return self._logger.debug(msg, *args, extra=self._inject_trace(extra), **kwargs)

    def exception(self, msg, *args, extra=None, **kwargs):
        return self._logger.exception(msg, *args, extra=self._inject_trace(extra), **kwargs)


def new_logger(name: str) -> TraceLogger:
    """
    Create a new logger with the given name.
    """
    Logger.init_logger()
    logger = logging.getLogger(name)
    logger.setLevel(get_env_logging_level())
    return _get_trace_logger(logger)


def _get_trace_logger(logger: logging.Logger) -> TraceLogger:
    """
    Create a new TraceLogger with the given logger and name.
    """
    return TraceLogger(logger)


