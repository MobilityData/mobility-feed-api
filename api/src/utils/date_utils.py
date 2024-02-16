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
