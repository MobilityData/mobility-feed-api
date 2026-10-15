import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from extractors.base import FileDataExtractor
from shared.database_gen.sqlacodegen_models import Feedinfo, Gtfsdataset

# feed_info.txt text columns (GTFS spec) mapped 1:1 onto Feedinfo string columns.
STRING_FIELDS = (
    "feed_publisher_name",
    "feed_publisher_url",
    "feed_lang",
    "default_lang",
    "feed_version",
    "feed_contact_email",
    "feed_contact_url",
)
# feed_info.txt date columns, stored as plain DATE (YYYYMMDD, no timezone).
DATE_FIELDS = ("feed_start_date", "feed_end_date")


def clean_str(value) -> Optional[str]:
    """Return a trimmed string, or None for empty/NaN/missing values."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def parse_gtfs_date(value) -> Optional[date]:
    """Parse a GTFS YYYYMMDD date. Returns None when missing or unparseable."""
    text = clean_str(value)
    if text is None:
        return None
    # pandas may read a purely numeric column as int/float, yielding "20240101.0".
    if text.endswith(".0"):
        text = text[:-2]
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        logging.warning("Unparseable feed_info date value: %r", value)
        return None


class FeedInfoExtractor(FileDataExtractor):
    """
    Extracts feed_info.txt into a Feedinfo row.

    One row per distinct feed_info.txt content, referenced by every dataset whose
    feed_info.txt has that content hash.
    """

    file_name = "feed_info.txt"

    @staticmethod
    def _get_by_hash(
        file_hash: Optional[str], db_session: Session
    ) -> Optional[Feedinfo]:
        if not file_hash:
            return None
        return (
            db_session.query(Feedinfo)
            .filter(Feedinfo.file_hash == file_hash)
            .one_or_none()
        )

    def has_data(self, dataset: Gtfsdataset, db_session: Session) -> bool:
        return dataset.feed_info_id is not None

    def link_existing_data(
        self, dataset: Gtfsdataset, file_hash: Optional[str], db_session: Session
    ) -> bool:
        feed_info = self._get_by_hash(file_hash, db_session)
        if feed_info is None:
            return False
        dataset.feed_info = feed_info
        logging.info(
            "Linked dataset %s to the feed_info already extracted for hash %s.",
            dataset.stable_id,
            file_hash,
        )
        return True

    def extract(
        self,
        df: pd.DataFrame,
        dataset: Gtfsdataset,
        file_hash: Optional[str],
        db_session: Session,
    ) -> None:
        if df is None or df.empty:
            logging.info(
                "feed_info.txt is empty for dataset %s; nothing to extract.",
                dataset.stable_id,
            )
            return
        if not file_hash:
            # Without a hash the row could not be matched to this file content
            # again, and a row per dataset is what the shared table avoids.
            raise ValueError(
                f"Cannot extract feed_info for dataset {dataset.stable_id}: "
                "the content hash of feed_info.txt is unknown."
            )

        # feed_info.txt holds a single record.
        row = df.iloc[0]

        values = {field: clean_str(row.get(field)) for field in STRING_FIELDS}
        for field in DATE_FIELDS:
            values[field] = parse_gtfs_date(row.get(field))

        # Upsert keyed by content hash: re-parsing the same file (for instance
        # after this extractor learns a new column) updates the row in place, and
        # every dataset already referencing it picks up the new values.
        feed_info = self._get_by_hash(file_hash, db_session)
        if feed_info is None:
            feed_info = Feedinfo(file_hash=file_hash)
            db_session.add(feed_info)

        for field, value in values.items():
            setattr(feed_info, field, value)
        dataset.feed_info = feed_info

        logging.info(
            "Extracted feed_info for dataset %s: start=%s end=%s",
            dataset.stable_id,
            values["feed_start_date"],
            values["feed_end_date"],
        )
