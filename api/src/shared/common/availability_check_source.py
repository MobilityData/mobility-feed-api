"""Who wrote a `gtfs_feed_availability_check` row, and which rows count as feed availability.

The table holds more than the daily availability check: failed nightly dataset downloads and
the download runs asked for by hand through the operations API are recorded there too, with
their request and response detail, so they can be debugged side by side.

Only the daily check answers "was the feed available". Every public reader of the table -
the `/v1/gtfs_feeds/{id}/availability` endpoint and the seal's `available` criterion, both in
the nightly run and in the backfill - filters through `feed_availability_checks_filter()`, so
changing which sources count is a single edit to `FEED_AVAILABILITY_SOURCES`. The operations
API is the one reader that sees every source.

This module is under `shared/common` so the API and every function that writes or reads the
table (`tasks_executor`, `batch_process_dataset`, `operations_api`) share one definition.
"""

from enum import Enum
from typing import Final, Tuple

from shared.database_gen.sqlacodegen_models import GtfsFeedAvailabilityCheck


class AvailabilityCheckSource(str, Enum):
    """Values stored in `gtfs_feed_availability_check.source`."""

    # The daily lightweight check run by tasks_executor.
    AVAILABILITY_CHECK = "availability_check"
    # A nightly dataset download that failed, recorded by batch_process_dataset.
    DATASET_DOWNLOAD = "dataset_download"
    # A run on the nightly job asked for through the operations API, download-only or full,
    # success included.
    DATASET_DOWNLOAD_MANUAL = "dataset_download_manual"


# The sources whose rows answer "was the feed available".
FEED_AVAILABILITY_SOURCES: Final[Tuple[AvailabilityCheckSource, ...]] = (AvailabilityCheckSource.AVAILABILITY_CHECK,)


def feed_availability_checks_filter():
    """SQLAlchemy clause keeping only the checks that count as feed availability."""
    return GtfsFeedAvailabilityCheck.source.in_([source.value for source in FEED_AVAILABILITY_SOURCES])
