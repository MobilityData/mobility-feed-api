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
"""Compliant criterion: the closest dataset validates with no errors."""

from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.common.seal_criteria import CriterionStatus, SealCriterionName
from shared.database_gen.sqlacodegen_models import (
    Gtfsdataset,
    Validationreport,
    t_validationreportgtfsdataset,
)
from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.history import (
    CompliantHistory,
    ValidationReport,
    ValidationReportHistory,
    load_dataset_history,
    range_bounds,
)
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator


class CompliantEvaluator(CriterionEvaluator):
    """`total_error = 0` on the latest validation report of the feed's closest dataset.

    A dataset with no report yet - unvalidated, or validation lagging publication - is UNKNOWN,
    which freezes the criterion at its last confirmed verdict rather than failing it. So is a feed
    with no dataset: a missing report is not a clean bill of health, nor evidence of one.
    """

    name = SealCriterionName.COMPLIANT

    def load_history(
        self,
        db_session: Session,
        feeds: Sequence,
        days: Sequence[date],
    ) -> Optional[CompliantHistory]:
        """The datasets over `days`, and every validation report of those datasets.

        Both are needed together: the report this criterion wants on a given day is the
        report of *that day's* closest dataset, and which dataset that is changes as a march
        proceeds.
        """
        if not feeds or not days:
            return CompliantHistory(
                load_dataset_history(db_session, feeds, days),
                ValidationReportHistory({}),
            )

        datasets = load_dataset_history(db_session, feeds, days)
        _, range_end = range_bounds(days)
        join_table = t_validationreportgtfsdataset
        rows = db_session.execute(
            select(
                join_table.c.dataset_id,
                Validationreport.id,
                Validationreport.validated_at,
                Validationreport.total_error,
            )
            .select_from(join_table)
            .join(
                Validationreport,
                Validationreport.id == join_table.c.validation_report_id,
            )
            # Reached through the dataset rather than through the feed, so one query covers
            # every dataset the march might resolve to without needing the ids up front.
            .join(Gtfsdataset, Gtfsdataset.id == join_table.c.dataset_id)
            .where(
                Gtfsdataset.feed_id.in_([feed.id for feed in feeds]),
                Validationreport.validated_at.is_not(None),
                Validationreport.validated_at <= range_end,
            )
        ).all()

        reports_by_dataset: Dict[str, List[ValidationReport]] = {}
        for row in rows:
            reports_by_dataset.setdefault(row.dataset_id, []).append(
                ValidationReport(
                    report_id=row.id,
                    dataset_id=row.dataset_id,
                    validated_at=row.validated_at,
                    total_error=row.total_error,
                )
            )
        return CompliantHistory(datasets, ValidationReportHistory(reports_by_dataset))

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        if ctx.history is None or not ctx.history.has_history_for(self.name):
            return (
                CriterionStatus.UNKNOWN,
                "compliant history was never loaded for this run - the context was built "
                "without calling load_history",
            )

        dataset = ctx.history.get_closest_dataset_at(ctx.feed_id, ctx.now)
        if dataset is None:
            return CriterionStatus.UNKNOWN, "the feed has no dataset"

        report = ctx.history.get_validation_report_at(dataset.dataset_id, ctx.now)
        if report is None:
            return (
                CriterionStatus.UNKNOWN,
                f"dataset {dataset.dataset_id} has no validation report",
            )

        if report.total_error is None:
            return (
                CriterionStatus.UNKNOWN,
                f"validation report {report.report_id} has no total_error",
            )

        validated = (
            f"dataset {report.dataset_id}, validated {report.validated_at.isoformat()}"
        )
        if report.total_error == 0:
            return CriterionStatus.PASS, f"no errors ({validated})"
        return CriterionStatus.FAIL, f"{report.total_error} error(s) ({validated})"
