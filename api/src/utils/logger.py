import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Final, Optional

from middleware.request_context import RequestContext, get_request_context
from utils.config import get_config, PROJECT_ID
from utils.dict_utils import get_safe_value

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
    latency: float
    protocol: str


@dataclass
class LogRecord:
    """
    Data class for Log Record
    """

    user_id: str
    httpRequest: dict
    trace: str
    spanId: str
    traceSampled: bool
    textPayload: Optional[str]
    jsonPayload: Optional[dict]


class AsyncStreamHandler(logging.StreamHandler):
    """
    Async Stream Handler
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop = asyncio.get_event_loop()

    def emit(self, record):
        """
        Emit the log record
        """
        asyncio.ensure_future(self.async_emit(record))

    async def async_emit(self, record):
        """
        Async emit the log record
        """
        msg = self.format(record)
        stream = self.stream
        await self.loop.run_in_executor(None, stream.write, msg)
        await self.loop.run_in_executor(None, stream.flush)


class GCPLogHandler(AsyncStreamHandler):
    """
    GCP Log Handler
    """

    def __init__(self):
        console_handler = logging.StreamHandler()
        self.logger = logging.getLogger()
        self.logger.addHandler(console_handler)
        self.logger.setLevel(logging.DEBUG)
        super().__init__()

    @staticmethod
    def get_trace(request_context: RequestContext):
        """
        Get the trace id from the log record
        """
        trace = ""
        trace_id = get_safe_value(request_context, "trace_id")
        if trace_id:
            trace = f"projects/{get_config(PROJECT_ID, '')}/traces/{trace_id}"
        return trace

    @staticmethod
    def get_http_request(record) -> HttpRequest:
        context = record.__getattribute__("context") if hasattr(record, "context") else None
        return context.get("http_request") if context else {}

    async def async_emit(self, record):
        """
        Emit the GCP log record
        """
        http_request = self.get_http_request(record)
        request_context = get_request_context()
        text_payload = None
        json_payload = None
        message = record.getMessage() if hasattr(record, "getMessage") else None
        if message:
            if isinstance(message, dict):
                json_payload = message
            else:
                text_payload = str(message)

        log_record: LogRecord = LogRecord(
            httpRequest=http_request.__dict__,
            trace=self.get_trace(request_context),
            spanId=request_context.get("span_id"),
            traceSampled=request_context.get("trace_sampled"),
            user_id=request_context.get("user_id"),
            textPayload=text_payload,
            jsonPayload=json_payload,
        )
        self.logger.info(json.dumps(log_record.__dict__))


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
        self.logger.setLevel(logging.DEBUG)

    def get_logger(self):
        """
        Get the logger instance
        :return: the logger instance
        """
        return self.logger
