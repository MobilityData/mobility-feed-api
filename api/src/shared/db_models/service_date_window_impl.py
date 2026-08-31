import datetime
from typing import Optional

from feeds_gen.models.service_date_window import ServiceDateWindow
from shared.common.continuous_coverage import as_date, window_days


class ServiceDateWindowImpl(ServiceDateWindow):
    """Implementation of the `ServiceDateWindow` model.

    A window is a pair of columns rather than a row of its own, so this class is built from the two
    dates instead of from an ORM object.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_dates(
        cls,
        start: Optional[datetime.date | datetime.datetime],
        end: Optional[datetime.date | datetime.datetime],
    ) -> Optional[ServiceDateWindow]:
        """Build a window from a start and end date, or None when either is missing.

        A half-open window is reported as no window at all: both bounds are required to say
        anything about coverage, and serving one bound would invite a client to treat it as a range.
        """
        start_date, end_date = as_date(start), as_date(end)
        if start_date is None or end_date is None:
            return None
        return cls(start=start_date, end=end_date, days=window_days(start_date, end_date))
