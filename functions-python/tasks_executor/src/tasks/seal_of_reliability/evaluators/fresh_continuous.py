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
"""Fresh (continuous coverage) criterion: successive datasets cover service with no gap."""

from datetime import date
from typing import Optional, Sequence, Tuple

from shared.common.continuous_coverage import (
    CALENDAR_FILES,
    FEED_INFO_FILE,
    MAX_COVERAGE_WINDOW,
    as_date,
    overlap_and_gap,
    window_days,
    within_max_coverage_window,
)
from shared.common.seal_criteria import CriterionStatus, SealCriterionName
from tasks.seal_of_reliability.context import DatasetCoverage, FeedSealContext
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator

Window = Tuple[date, date]

CALENDAR_FILE_LIST = " or ".join(CALENDAR_FILES)


def _window(start, end) -> Optional[Window]:
    """Two plain dates, or None when the window is incomplete or inverted."""
    start, end = as_date(start), as_date(end)
    return (start, end) if window_days(start, end) is not None else None


def _declared_window(dataset: DatasetCoverage) -> Optional[Window]:
    return _window(dataset.feed_info_start, dataset.feed_info_end)


def _service_window(dataset: DatasetCoverage) -> Optional[Window]:
    return _window(dataset.service_date_range_start, dataset.service_date_range_end)


def _span(window: Window) -> str:
    return f"{window[0].isoformat()} to {window[1].isoformat()}"


def _calendar_verdict(
    pair: Sequence[DatasetCoverage], declared_note: str
) -> Tuple[CriterionStatus, str]:
    """What the validated service windows say, prefixed with `declared_note`."""
    service = [_service_window(dataset) for dataset in pair]
    missing = [dataset for dataset, window in zip(pair, service) if window is None]
    if missing:
        # no calendar file is the producer's omission; a window we never derived is ours
        unpublished = [
            dataset.dataset_id for dataset in missing if not dataset.has_calendar_data
        ]
        if unpublished:
            return (
                CriterionStatus.FAIL,
                f"{declared_note}, and dataset {', '.join(unpublished)} carries no "
                f"{CALENDAR_FILE_LIST}",
            )
        return (
            CriterionStatus.UNKNOWN,
            f"{declared_note}, and dataset "
            f"{', '.join(dataset.dataset_id for dataset in missing)} has no validated "
            "service window yet",
        )

    _, gap_days = overlap_and_gap(service[0][1], service[1][0])
    if gap_days is None:
        return (
            CriterionStatus.PASS,
            f"{declared_note}, and the validated service windows leave no gap",
        )
    return (
        CriterionStatus.FAIL,
        f"{declared_note}, and the validated service windows leave a {gap_days}-day gap",
    )


class FreshContinuousEvaluator(CriterionEvaluator):
    """Successive datasets cover service with no uncovered day between them (#1782).

    Three steps, in order:

    1. The closest dataset's window - its `feed_info.txt` range, or its validated service
       window when it declares none - must be no longer than `MAX_COVERAGE_WINDOW`.
    2. A feed with only that one dataset passes: there is no boundary to break yet.
    3. Otherwise, the boundary against the previous dataset decides. The declared ranges rule
       where both datasets declare one, and the validated service windows are what excuses a
       declared gap and the whole answer with no declared range. A gap has to show in both to
       fail.

    A boundary that needs the calendar where a dataset shipped no calendar file is a FAIL. It
    is UNKNOWN only when the file is there, and we have not derived a window from it yet.
    """

    name = SealCriterionName.FRESH_CONTINUOUS

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        newer = ctx.closest_dataset
        if newer is None:
            return CriterionStatus.UNKNOWN, "the feed has no dataset"

        # 1. the maximum coverage window, on the closest dataset alone
        declared = _declared_window(newer)
        window = declared or _service_window(newer)
        if window is not None and within_max_coverage_window(*window) is False:
            return (
                CriterionStatus.FAIL,
                f"dataset {newer.dataset_id} covers {_span(window)}, longer than the "
                f"{MAX_COVERAGE_WINDOW.days}-day maximum coverage window",
            )
        elif window is None:
            return (
                CriterionStatus.UNKNOWN,
                f"Unknown coverage window for dataset {newer.dataset_id}",
            )

        # 2. nothing published before it, so no boundary to judge
        older = ctx.previous_dataset
        if older is None:
            return (
                CriterionStatus.PASS,
                f"dataset {newer.dataset_id} is the feed's only dataset as of this run",
            )

        # 3. the declared ranges, where both datasets declare one
        pair = (older, newer)
        older_declared = _declared_window(older)
        if declared is None or older_declared is None:
            return _calendar_verdict(
                pair, f"the datasets do not both declare a {FEED_INFO_FILE} range"
            )

        _, gap_days = overlap_and_gap(older_declared[1], declared[0])
        if gap_days is None:
            return (
                CriterionStatus.PASS,
                f"the declared {FEED_INFO_FILE} ranges leave no gap",
            )
        return _calendar_verdict(
            pair, f"the declared {FEED_INFO_FILE} ranges leave a {gap_days}-day gap"
        )
