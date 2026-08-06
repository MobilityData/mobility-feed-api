from abc import ABC, abstractmethod

import pandas as pd
from sqlalchemy.orm import Session

from shared.database_gen.sqlacodegen_models import Gtfsdataset


class FileDataExtractor(ABC):
    """
    Base class for extracting structured data from a single GTFS file.

    Each subclass handles exactly one GTFS file (identified by ``file_name``)
    and persists the extracted values to the database.

    To add support for a new file:
      1. Implement a subclass here and register it in ``extractors/registry.py``.
      2. Add the file name to ``EXTRACTABLE_FILES`` in batch_process_dataset's
         ``pipeline_tasks.py`` so the producer enqueues a task for it.
    """

    #: The GTFS file this extractor handles, e.g. "feed_info.txt".
    file_name: str

    @abstractmethod
    def extract(
        self, df: pd.DataFrame, dataset: Gtfsdataset, db_session: Session
    ) -> None:
        """
        Parse ``df`` (the parsed contents of ``file_name``) and persist the
        extracted data for ``dataset``. Implementations must be idempotent:
        re-running for the same dataset should update, not duplicate.
        """
        raise NotImplementedError
