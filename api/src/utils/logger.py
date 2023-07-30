import logging


class Logger:
    """
    Util class for logging information, errors or warnings
    """
    def __init__(self, name):
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')

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
