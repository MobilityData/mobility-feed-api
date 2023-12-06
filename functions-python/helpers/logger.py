import google.cloud.logging
from google.cloud.logging_v2 import Client


class Logger:
    """
    Util class for logging information, errors or warnings.
    This class uses the Google Cloud Logging API enhancing the logs with extra request information.
    """

    def __init__(self, name):
        self.init_logger()
        self.logger = self.init_logger().logger(name)

    @staticmethod
    def init_logger() -> Client:
        """
        Initializes the logger
        """
        client = google.cloud.logging.Client()
        client.get_default_handler()
        client.setup_logging()
        return client

    def get_logger(self) -> Client:
        """
        Get the GCP logger instance
        :return: the logger instance
        """
        return self.logger
