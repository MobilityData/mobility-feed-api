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
    """Extracts feed_info.txt into a Feedinfo row (one per dataset)."""

    file_name = "feed_info.txt"

    def extract(
        self, df: pd.DataFrame, dataset: Gtfsdataset, db_session: Session
    ) -> None:
        if df is None or df.empty:
            logging.info(
                "feed_info.txt is empty for dataset %s; nothing to extract.",
                dataset.stable_id,
            )
            return

        # feed_info.txt holds a single record.
        row = df.iloc[0]

        values = {field: clean_str(row.get(field)) for field in STRING_FIELDS}
        for field in DATE_FIELDS:
            values[field] = parse_gtfs_date(row.get(field))

        # Upsert keyed by dataset so reprocessing updates in place.
        feed_info = (
            db_session.query(Feedinfo)
            .filter(Feedinfo.gtfs_dataset_id == dataset.id)
            .one_or_none()
        )
        if feed_info is None:
            feed_info = Feedinfo(gtfs_dataset_id=dataset.id)
            db_session.add(feed_info)

        for field, value in values.items():
            setattr(feed_info, field, value)

        logging.info(
            "Extracted feed_info for dataset %s: start=%s end=%s",
            dataset.stable_id,
            values["feed_start_date"],
            values["feed_end_date"],
        )
