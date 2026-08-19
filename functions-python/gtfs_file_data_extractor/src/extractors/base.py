from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from shared.database_gen.sqlacodegen_models import Gtfsdataset


class FileDataExtractor(ABC):
    """
    Base class for extracting structured data from a single GTFS file.

    Each subclass handles exactly one GTFS file (identified by ``file_name``)
    and persists the extracted values to the database.

    Extracted data is keyed by the content hash of the file it came from and
    shared by every dataset whose copy of the file has that hash, so a dataset
    whose file did not change is linked to the existing data instead of getting
    a duplicate of it.

    To add support for a new file:
      1. Implement a subclass here and register it in ``extractors/registry.py``.
      2. Add the file name to ``EXTRACTABLE_FILES`` in batch_process_dataset's
         ``pipeline_tasks.py`` so the producer enqueues a task for it.
    """

    # The GTFS file this extractor handles, e.g. "feed_info.txt".
    file_name: str

    @abstractmethod
    def extract(
        self,
        df: pd.DataFrame,
        dataset: Gtfsdataset,
        file_hash: Optional[str],
        db_session: Session,
    ) -> None:
        """
        Parse ``df`` (the parsed contents of ``file_name``, whose content hash is
        ``file_hash``), persist the extracted data and link ``dataset`` to it.

        Implementations must be idempotent: re-running for the same content
        updates the existing data in place rather than duplicating it.
        """
        raise NotImplementedError

    @abstractmethod
    def has_data(self, dataset: Gtfsdataset, db_session: Session) -> bool:
        """Whether ``dataset`` is already linked to this extractor's data."""
        raise NotImplementedError

    @abstractmethod
    def link_existing_data(
        self, dataset: Gtfsdataset, file_hash: Optional[str], db_session: Session
    ) -> bool:
        """
        Link ``dataset`` to data already extracted from a file with the same
        content hash, and return whether such data was found.

        This is what gives a dataset whose file did not change its own reference
        to the data, without downloading and re-parsing the file. Returns False
        when nothing has been extracted for this content yet, or when the hash is
        unknown — in both cases the caller must extract from the file itself.
        """
        raise NotImplementedError
