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
"""Contract tests pinning the job's seal enums to the database types. No database connection.

The job writes `seal_criterion.criterion`, `observed_status` and `confirmed_status` from its own
`SealCriterionName` / `CriterionStatus` enums, and the read API serves those stored values straight
through to clients (the API `status` enum is the DB enum verbatim). So a value added here that the
database type does not have, or vice versa, breaks either the write or the read - and the read API
raises on a criterion it does not recognise rather than hiding it.

These tests compare against the SQLAlchemy Enum types in the generated models, which are generated
from the Liquibase changelog, so the assertion is against the real schema and needs no live DB.
Adding a criterion or status means updating, in lockstep: the Liquibase enum, the API's
`SealCriterionName` and status constants, `docs/DatabaseCatalogAPI.yaml`, and the enums here.
"""

import unittest

from shared.database_gen.sqlacodegen_models import SealCriterion
from tasks.seal_of_reliability.criteria import CriterionStatus, SealCriterionName


def db_enum_values(column_name: str) -> set:
    """The values of the Postgres enum backing a `seal_criterion` column."""
    return set(SealCriterion.__table__.c[column_name].type.enums)


class TestSealEnumContract(unittest.TestCase):
    """The job's enums must mirror the `seal_criterion_name` / `seal_criterion_status` DB types."""

    def test_criterion_names_match_db_enum(self):
        """`SealCriterionName` is the full `seal_criterion_name` type, no more and no less."""
        assert {criterion.value for criterion in SealCriterionName} == db_enum_values(
            "criterion"
        )

    def test_statuses_match_db_enum(self):
        """`CriterionStatus` is the full `seal_criterion_status` type, no more and no less."""
        assert {status.value for status in CriterionStatus} == db_enum_values(
            "observed_status"
        )

    def test_observed_and_confirmed_share_one_status_type(self):
        """Both status columns are the same enum, so one set of values covers writing either."""
        assert db_enum_values("observed_status") == db_enum_values("confirmed_status")

    def test_verdict_statuses_are_pass_and_fail(self):
        """`is_verdict` must stay pinned to exactly the two values that mean the check answered.

        A new status defaulting into "verdict" would silently start driving the seal roll-up.
        """
        assert {status.value for status in CriterionStatus if status.is_verdict} == {
            "pass",
            "fail",
        }
