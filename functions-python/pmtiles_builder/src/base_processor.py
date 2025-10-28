from fast_csv_parser import FastCsvParser
from shared.helpers.utils import detect_encoding
from shared.helpers.runtime_metrics import track_metrics
import os


class BaseProcessor:
    """
    Minimal base class for processors that read a GTFS CSV and write derived outputs.

    Responsibilities
    - Resolve the absolute path of the input file via the shared CsvCache.
    - Detect file encoding and initialize a fast CSV parser.
    - Provide a safe early-return when the input file is absent (some GTFS files are optional).
    - Delegate the actual line-by-line work to subclasses via `process_file()`.

    Lifecycle contract
    - Subclasses should override `process_file(self)` — do not call it directly.

    Notes on flags
    - `no_download` and `no_delete` are orchestration hints used by the caller (e.g., the builder) to
      decide whether to download the source file and whether to delete it afterward. The base class does
      not use these flags directly; they are honored by the orchestrator.
    """

    def __init__(
        self, filename, csv_cache, logger=None, no_download=False, no_delete=False
    ):
        self.filename = filename
        self.csv_cache = csv_cache
        self.logger = logger or csv_cache.logger
        self.no_download = no_download
        self.no_delete = no_delete

        # Will be populated during `process()`
        self.filepath = None
        self.csv_parser = None
        self.encoding = None

    @track_metrics(metrics=("time", "memory", "cpu"))
    def process(self):
        """
        Entry point called by orchestrators to run a processor in a safe, uniform way.
\
        """
        self.filepath = self.csv_cache.get_path(self.filename)
        # If the target file does not exist in the workdir, skip processing.
        # This avoids exceptions for optional files and keeps pipelines resilient.
        if not os.path.exists(self.filepath):
            # We don't return an Exception here because the presence of mandatory files has been verified elsewhere.
            self.logger.debug(
                "File not present, skipping processing: %s", self.filepath
            )
            return
        self.csv_parser = FastCsvParser()
        self.encoding = detect_encoding(filename=self.filepath, logger=self.logger)
        self.logger.debug("Begin processing file %s", self.filename)
        self.process_file()

    def process_file(self):
        """
        Hook for subclasses to implement the actual processing logic.

        Contract
        - May assume `self.filepath`, `self.csv_parser`, and `self.encoding` are initialized.
        - Should handle empty files gracefully (e.g., by returning early).
        - Should not raise on benign format issues where possible; prefer logging and continue.
        """
        pass
