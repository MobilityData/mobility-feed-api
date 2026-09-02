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

from typing import Tuple

from shared.common.seal_criteria import CriterionStatus, SealCriterionName
from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator


class CompliantEvaluator(CriterionEvaluator):
    """`total_error = 0` on the latest validation report of the feed's closest dataset.

    A dataset with no report yet - unvalidated, or validation lagging publication - is UNKNOWN,
    which freezes the criterion at its last confirmed verdict rather than failing it. So is a feed
    with no dataset: a missing report is not a clean bill of health, nor evidence of one.
    """

    name = SealCriterionName.COMPLIANT

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        if ctx.closest_dataset is None:
            return CriterionStatus.UNKNOWN, "the feed has no dataset"

        report = ctx.latest_validation_report
        if report is None:
            return (
                CriterionStatus.UNKNOWN,
                f"dataset {ctx.closest_dataset.dataset_id} has no validation report",
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
