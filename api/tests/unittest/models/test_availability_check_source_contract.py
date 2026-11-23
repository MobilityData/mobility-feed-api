"""Contract tests pinning `gtfs_feed_availability_check.source` values. No database connection.

`shared.common.availability_check_source` is the single definition of the sources the
functions write and of the ones that count as feed availability. The public availability
endpoint and the Seal of Reliability both filter through it; the operations API exposes every
source as an enum on its `source` filter.

Adding a source means updating, in lockstep: `AvailabilityCheckSource` and the
`availability_source` parameter in `docs/OperationsAPI.yaml` plus a stub regen.
"""

import unittest
from pathlib import Path

import yaml

from shared.common.availability_check_source import (
    FEED_AVAILABILITY_SOURCES,
    AvailabilityCheckSource,
    feed_availability_checks_filter,
)
from shared.database_gen.sqlacodegen_models import GtfsFeedAvailabilityCheck

OPERATIONS_SPEC = Path(__file__).resolve().parents[4] / "docs" / "OperationsAPI.yaml"


class TestAvailabilityCheckSourceContract(unittest.TestCase):
    def test_only_the_daily_check_counts_as_feed_availability(self):
        """Changing this changes the public endpoint and the seal; it should be deliberate."""
        self.assertEqual(FEED_AVAILABILITY_SOURCES, (AvailabilityCheckSource.AVAILABILITY_CHECK,))

    def test_filter_selects_the_feed_availability_sources(self):
        clause = feed_availability_checks_filter()
        compiled = clause.compile(compile_kwargs={"literal_binds": True})
        self.assertEqual(clause.left.table.name, GtfsFeedAvailabilityCheck.__tablename__)
        self.assertEqual(clause.left.name, "source")
        self.assertIn("'availability_check'", str(compiled))
        for source in set(AvailabilityCheckSource) - set(FEED_AVAILABILITY_SOURCES):
            self.assertNotIn(f"'{source.value}'", str(compiled))

    def test_operations_spec_lists_every_source(self):
        spec = yaml.safe_load(OPERATIONS_SPEC.read_text())
        parameter = spec["components"]["parameters"]["availability_source"]
        self.assertEqual(
            set(parameter["schema"]["items"]["enum"]),
            {source.value for source in AvailabilityCheckSource},
        )

    def test_db_default_is_the_daily_check(self):
        """A row written without a source must still count as an availability check."""
        column = GtfsFeedAvailabilityCheck.__table__.c.source
        self.assertFalse(column.nullable)
        self.assertIn(AvailabilityCheckSource.AVAILABILITY_CHECK.value, str(column.server_default.arg))
