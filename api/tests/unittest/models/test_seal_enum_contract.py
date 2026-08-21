"""Contract tests pinning the API's seal enums to the database types. No database connection.

The API serves `seal_criterion.observed_status` straight through as the `status` field, and resolves
`seal_criterion.criterion` into `SealCriterionName`. So a value the nightly job can write but this
build does not know about is a real incompatibility: the criterion case now raises rather than
quietly dropping the criterion from the report, and a status the generated model rejects would fail
response validation.

The assertions compare against the SQLAlchemy Enum types in the generated models, which come from
the Liquibase changelog, so this checks the real schema without a live DB. The nightly job has the
mirror of these tests over its own enums, in
`functions-python/tasks_executor/tests/tasks/seal_of_reliability/test_seal_enum_contract.py`.

Adding a criterion or status means updating, in lockstep: the Liquibase enum, `SealCriterionName`
and the status constants here, `docs/DatabaseCatalogAPI.yaml` (plus a stub regen), and the job enums.
"""

import unittest

from feeds_gen.models.reliability_criterion import ReliabilityCriterion
from shared.common.seal_criteria import (
    GRACE_PERIODS,
    PROBATION_PERIODS,
    SealCriterionName,
)
from shared.database_gen.sqlacodegen_models import SealCriterion
from shared.db_models.reliability_criterion_impl import (
    STATUS_FAIL,
    STATUS_NEVER_EVALUATED,
    STATUS_NOT_APPLICABLE,
    STATUS_PASS,
    STATUS_UNKNOWN,
)

API_STATUSES = {
    STATUS_PASS,
    STATUS_FAIL,
    STATUS_UNKNOWN,
    STATUS_NEVER_EVALUATED,
    STATUS_NOT_APPLICABLE,
}


def db_enum_values(column_name: str) -> set:
    """The values of the Postgres enum backing a `seal_criterion` column."""
    return set(SealCriterion.__table__.c[column_name].type.enums)


class TestSealEnumContract(unittest.TestCase):
    """The API's criterion and status enums must mirror the `seal_criterion` DB types."""

    def test_criterion_names_match_db_enum(self):
        """`SealCriterionName` is the full `seal_criterion_name` type, no more and no less."""
        assert {criterion.value for criterion in SealCriterionName} == db_enum_values("criterion")

    def test_status_constants_match_db_enum(self):
        """The API `status` values are the `seal_criterion_status` type verbatim.

        There is no DB-to-API translation left, so any divergence would be served raw to clients.
        """
        assert API_STATUSES == db_enum_values("observed_status")

    def test_every_db_status_passes_response_validation(self):
        """Every status the job can store must be accepted by the generated response model.

        This is the direction that breaks in production: the job writes a status, the API reads it
        back and would fail validating its own response.
        """
        for status in sorted(db_enum_values("observed_status")):
            with self.subTest(status=status):
                assert ReliabilityCriterion.status_validate_enum(status) == status

    def test_unknown_status_is_rejected_by_response_validation(self):
        """The generated validator is a real enum check, so the test above cannot pass vacuously."""
        with self.assertRaises(ValueError):
            ReliabilityCriterion.status_validate_enum("some_future_status")

    def test_every_criterion_passes_response_validation(self):
        """Likewise for the criterion names the job can store."""
        for criterion in sorted(db_enum_values("criterion")):
            with self.subTest(criterion=criterion):
                assert ReliabilityCriterion.criterion_validate_enum(criterion) == criterion

    def test_policy_maps_cover_every_criterion(self):
        """Every criterion needs a grace and probation entry, even if the window is None.

        `GRACE_PERIODS.get()` would silently return None for a criterion missing from the map,
        turning it into a no-grace criterion by accident rather than by decision.
        """
        assert set(GRACE_PERIODS) == set(SealCriterionName)
        assert set(PROBATION_PERIODS) == set(SealCriterionName)
