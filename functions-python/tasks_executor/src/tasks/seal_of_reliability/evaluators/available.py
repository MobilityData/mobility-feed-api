#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Available criterion: the feed's producer URL answered today."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.common.seal_criteria import (
    AVAILABILITY_LOOKBACK,
    CriterionStatus,
    SealCriterionName,
)
from shared.database_gen.sqlacodegen_models import GtfsFeedAvailabilityCheck
from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.history import (
    AvailabilityCheck,
    AvailabilityHistory,
    FeedIdStr,
)
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator


class AvailableEvaluator(CriterionEvaluator):
    """The latest `gtfs_feed_availability_check` in the 24 hours up to `now` has `success`.

    A window with no check at all is UNKNOWN, not a failure: it means we did not look, not
    that the feed was down.

    Its data varies by day, so it loads its own history rather than reading a single answer
    off the context - see the `context` module docstring on the three kinds of input.
    """

    name = SealCriterionName.AVAILABLE

    def load_history(
        self,
        db_session: Session,
        feeds: Sequence,
        days: Sequence[date],
    ) -> Optional[AvailabilityHistory]:
        """Load every availability check for all the feeds and days, in one query."""
        if not feeds or not days:
            return AvailabilityHistory({})

        feed_ids = [feed.id for feed in feeds]
        # The march evaluates at each day's start, while a nightly run evaluates part-way
        # through its day, so the range closes at the end of the last day either way.
        range_start = (
            datetime.combine(min(days), time.min, tzinfo=timezone.utc)
            - AVAILABILITY_LOOKBACK
        )
        range_end = datetime.combine(
            max(days), time.min, tzinfo=timezone.utc
        ) + timedelta(days=1)

        rows = db_session.execute(
            select(
                GtfsFeedAvailabilityCheck.feed_id,
                GtfsFeedAvailabilityCheck.checked_at,
                GtfsFeedAvailabilityCheck.success,
            ).where(
                GtfsFeedAvailabilityCheck.feed_id.in_(feed_ids),
                GtfsFeedAvailabilityCheck.checked_at > range_start,
                GtfsFeedAvailabilityCheck.checked_at <= range_end,
            )
        ).all()

        checks_by_feed: Dict[FeedIdStr, List[AvailabilityCheck]] = {}
        for row in rows:
            checks_by_feed.setdefault(row.feed_id, []).append(
                AvailabilityCheck(checked_at=row.checked_at, success=bool(row.success))
            )
        return AvailabilityHistory(checks_by_feed)

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        if ctx.history is None or not ctx.history.has_history_for(self.name):
            # Not a data condition: the context was built without running this criterion's
            # loader. Said out loud rather than passed off as a missing check, because the two
            # look identical in the stored row and only this one is a bug.
            return (
                CriterionStatus.UNKNOWN,
                "available history was never loaded for this run - the context was built "
                "without calling load_history",
            )

        check = ctx.history.get_latest_availability_check_at(
            ctx.feed_id, ctx.now, AVAILABILITY_LOOKBACK
        )
        if check is None:
            since = (ctx.now - AVAILABILITY_LOOKBACK).isoformat()
            return CriterionStatus.UNKNOWN, f"no availability check since {since}"

        status = CriterionStatus.PASS if check.success else CriterionStatus.FAIL
        outcome = "succeeded" if check.success else "failed"
        return status, f"the check at {check.checked_at.isoformat()} {outcome}"
