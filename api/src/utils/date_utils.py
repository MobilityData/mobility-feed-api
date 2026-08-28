from datetime import datetime, timezone
from typing import Final, Optional
import re

iso_pattern: Final[str] = (
    r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])T([01]\d|2[0-3]):([0-5]\d):([0-5]\d)("
    r"\.\d+)?(Z|[+-](["
    r"01]\d|2[0-3]):([0-5]\d))?$"
)


def valid_iso_date(date_string: Optional[str]) -> bool:
    """Check if a date string is a valid ISO 8601 date format."""
    # Validators are not required to check for None or empty strings
    if date_string is None or date_string.strip() == "":
        return True
    return re.match(iso_pattern, date_string) is not None


def parse_iso_datetime(date_string: Optional[str]) -> Optional[datetime]:
    """Parse a `valid_iso_date`-validated string, defaulting to UTC when it carries no offset.

    `valid_iso_date`'s offset group is optional, so `2024-01-01T00:00:00` and
    `2024-01-01T00:00:00Z` are equally valid input, but `fromisoformat` returns a naive datetime
    for the first and a timezone-aware one for the second - comparing one of each raises
    `TypeError`. Normalizing here means two independently-parsed values are always comparable.
    """
    if not date_string:
        return None
    parsed = datetime.fromisoformat(date_string)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
