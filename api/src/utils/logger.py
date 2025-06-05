import logging
import os
import sys
from dataclasses import dataclass, asdict
from typing import Final, Optional

from middleware.request_context import RequestContext, get_request_context
from shared.common.logging_utils import get_env_logging_level
from utils.config import get_config, PROJECT_ID
from utils.dict_utils import get_safe_value

import google.cloud.logging
from google.cloud.logging_v2.handlers import CloudLoggingFilter, CloudLoggingHandler

API_ACCESS_LOG: Final[str] = "api-access-log"
CLOUD_RUN_SERVICE_ID: Final[str] = "K_SERVICE"
CLOUD_RUN_REVISION_ID: Final[str] = "K_REVISION"
CLOUD_RUN_CONFIGURATION_ID: Final[str] = "K_CONFIGURATION"


@dataclass
class HttpRequest:
    """
    Data class for HTTP Request logging
    """

    requestMethod: str
    requestUrl: str
    status: int
    responseSize: int
    userAgent: str
    remoteIp: str
    serverIp: str
    latency: str
    protocol: str


def get_trace(request_context: RequestContext):
    """
    Get the trace id from the log record
    """
    trace = ""
    trace_id = get_safe_value(request_context, "trace_id")
    if trace_id:
        trace = f"projects/{get_config(PROJECT_ID, '')}/traces/{trace_id}"
    return trace


def get_http_request(record) -> HttpRequest | None:
    """
    Get the http request from the log record
    If the http request is not found, return None
    """
    context = record.__getattribute__("context") if hasattr(record, "context") else None
    return context.get("http_request") if context else {}


class GoogleCloudLogFilter(CloudLoggingFilter):
    """
    Log filter for Google Cloud Logging.
    This filter adds the trace, span and http_request fields to the log record.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            request_context = get_request_context()
            http_request = get_http_request(record)
            if http_request:
                record.http_request = asdict(http_request)
            span_id = request_context.get("span_id")
            trace = get_trace(request_context)
            record.trace = trace
            record.span_id = span_id

            record._log_fields = {
                "logging.googleapis.com/trace": trace,
                "logging.googleapis.com/spanId": span_id,
                "logging.googleapis.com/httpRequest": asdict(http_request) if http_request else None,
                "logging.googleapis.com/trace_sampled": True,
            }
            super().filter(record)
        except Exception as e:
            # Using print to avoid a recursive call the log filter
            print(f"Error in GoogleCloudLogFilter: {e}")
        return True


class StderrToLog:
    """
    Redirect stderr to log
    """

    def __init__(self, logger):
        self.logger = logger

    def write(self, message):
        message = message.strip()
        if message:
            self.logger.error(message)

    def flush(self):
        pass


def get_logger(name: Optional[str]):
    """
    Returns a logger with the name making sure the propagate flag is set to True.
    """
    logger = logging.getLogger(name)
    logger.propagate = True
    return logger


def is_local_env():
    """
    Returns: True if the environment is local, False otherwise
    """
    return os.getenv("K_SERVICE") is None


def global_logging_setup():
    logging.debug("Starting cloud up logging")
    if is_local_env():
        logging.debug("Setting local up logging")
        logging.basicConfig(level=get_env_logging_level())
        return
    logging.debug("Setting cloud up logging")
    # Send warnings through logging
    logging.captureWarnings(True)
    # Replace sys.stderr
    sys.stderr = StderrToLog(logging.getLogger("stderr"))
    try:
        client = google.cloud.logging.Client()
        handler = CloudLoggingHandler(client, structured=True)
        handler.setLevel(logging.DEBUG)
        handler.addFilter(GoogleCloudLogFilter(project=client.project))
    except Exception as e:
        logging.error("Error initializing cloud logging: %s", e)
        logging.basicConfig(level=get_env_logging_level())
        return

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # This overrides individual logs essential for debugging purposes.
    for name in [
        "sqlalchemy",
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "sqlalchemy.exc",
        "feed-api",
        "sqlalchemy.engine",
    ]:
        get_logger(name)

    logging.debug("Setting cloud up logging completed")
