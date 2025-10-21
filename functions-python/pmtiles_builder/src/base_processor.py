from fast_csv_parser import FastCsvParser
from shared.helpers.utils import detect_encoding
from shared.helpers.runtime_metrics import track_metrics
import os


class BaseProcessor:
    def __init__(
        self, filename, csv_cache, logger=None, no_download=False, no_delete=False
    ):
        self.filename = filename
        self.csv_cache = csv_cache
        self.logger = logger or csv_cache.logger
        self.no_download = no_download
        self.no_delete = no_delete

        self.filepath = None
        self.csv_parser = None
        self.encoding = None

    @track_metrics(metrics=("time", "memory", "cpu"))
    def process(self):
        self.filepath = self.csv_cache.get_path(self.filename)
        # If the target file does not exist in the workdir, skip processing.
        if not os.path.exists(self.filepath):
            self.logger.debug(
                "File not present, skipping processing: %s", self.filepath
            )
            return
        self.csv_parser = FastCsvParser()
        self.encoding = detect_encoding(filename=self.filepath, logger=self.logger)
        self.logger.debug(f"Begin processing file {self.filename}: ")
        self.process_file()

    def process_file(self):
        pass
