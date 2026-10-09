#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Both ways of getting this wrong are silent, so both are pinned."""

import unittest

from unittest.mock import MagicMock, patch

from sizing import (
    LARGEST,
    Basis,
    FailureKind,
    Size,
    Tier,
    choose_size,
    describe,
    first_known,
    function_name,
    classify_failure,
    escalate,
    measure_dataset,
    queue_env_var,
    size_for_dataset,
)

CONFIG_VALUE = "sizing.get_config_value"

MB = 1024**2
GB = 1024**3
TIERS = (
    Tier(size=Size.S, max_bytes=256 * MB),
    Tier(size=Size.M, max_bytes=2 * GB),
    Tier(size=Size.L, max_bytes=None),
)


class TestChooseSize(unittest.TestCase):
    def test_the_smallest_band_is_the_smallest_worker(self):
        self.assertEqual(choose_size(1, TIERS), Size.S)
        self.assertEqual(choose_size(256 * MB - 1, TIERS), Size.S)

    def test_the_middle_band(self):
        self.assertEqual(choose_size(256 * MB, TIERS), Size.M)
        self.assertEqual(choose_size(2 * GB - 1, TIERS), Size.M)

    def test_each_threshold_is_exclusive(self):
        """A measure exactly at a bound belongs to the rung above it."""
        self.assertEqual(choose_size(256 * MB, TIERS), Size.M)
        self.assertEqual(choose_size(2 * GB, TIERS), Size.L)

    def test_over_the_last_threshold_is_the_large_worker(self):
        self.assertEqual(choose_size(10 * GB, TIERS), Size.L)

    def test_an_unknown_measure_routes_to_the_largest(self):
        """Size columns are nullable with no backfill, so None is an ordinary answer.

        Guessing small here turns a missing row into an OOM.
        """
        self.assertEqual(choose_size(None, TIERS), LARGEST)
        self.assertEqual(LARGEST, Size.L)

    def test_zero_is_not_treated_as_unknown(self):
        """A genuinely empty dataset is small, not unmeasured."""
        self.assertEqual(choose_size(0, TIERS), Size.S)


class TestOverride(unittest.TestCase):
    """A configured size is the answer; the measurement is not consulted."""

    def test_it_can_raise_the_measured_size(self):
        self.assertEqual(choose_size(1, TIERS, override=Size.L), Size.L)

    def test_it_can_skip_a_rung(self):
        self.assertEqual(choose_size(10 * GB, TIERS, override=Size.S), Size.S)

    def test_it_can_lower_the_measured_size(self):
        """Whoever set the config has looked at the feed; the table is a heuristic."""
        self.assertEqual(choose_size(10 * GB, TIERS, override=Size.M), Size.M)

    def test_it_applies_to_an_unknown_measure(self):
        self.assertEqual(choose_size(None, TIERS, override=Size.M), Size.M)

    def test_matching_the_measured_size_changes_nothing(self):
        self.assertEqual(choose_size(1, TIERS, override=Size.S), Size.S)


class TestParse(unittest.TestCase):
    def test_accepts_the_written_forms(self):
        for raw in ("l", "L", " l ", "l\n"):
            with self.subTest(raw=raw):
                self.assertEqual(Size.parse(raw), Size.L)

    def test_accepts_every_size(self):
        for raw, expected in (("s", Size.S), ("m", Size.M), ("l", Size.L)):
            with self.subTest(raw=raw):
                self.assertEqual(Size.parse(raw), expected)

    def test_unset_is_none(self):
        self.assertIsNone(Size.parse(None))

    def test_nonsense_is_ignored_rather_than_fatal(self):
        """Config is operator-entered; a typo must not fail the request."""
        for raw in ("xl", "", "3", {}, []):
            with self.subTest(raw=raw):
                self.assertIsNone(Size.parse(raw))


class TestFirstKnown(unittest.TestCase):
    def test_returns_the_first_usable_value(self):
        self.assertEqual(first_known(None, 0, 42, 99), 42)

    def test_zero_and_none_are_not_measurements(self):
        self.assertIsNone(first_known(None, 0, None))

    def test_unparsable_values_are_skipped(self):
        self.assertEqual(first_known("not a number", 7), 7)

    def test_nothing_known(self):
        self.assertIsNone(first_known())


class TestNaming(unittest.TestCase):
    def test_queue_env_var(self):
        self.assertEqual(
            queue_env_var("PARQUET_BUILDER", Size.S), "PARQUET_BUILDER_QUEUE_S"
        )
        self.assertEqual(
            queue_env_var("PARQUET_BUILDER", Size.M), "PARQUET_BUILDER_QUEUE_M"
        )
        self.assertEqual(
            queue_env_var("PARQUET_BUILDER", Size.L), "PARQUET_BUILDER_QUEUE_L"
        )

    def test_function_name(self):
        self.assertEqual(
            function_name("parquet-builder", Size.L, "dev"), "parquet-builder-l-dev"
        )

    def test_describe_is_loggable(self):
        self.assertEqual(describe(TIERS), f"s<{256 * MB}, m<{2 * GB}, l:rest")


class TestLadder(unittest.TestCase):
    def test_the_largest_is_the_last_rung(self):
        self.assertEqual(LARGEST, Size.L)
        self.assertEqual([s.value for s in Size], ["s", "m", "l"])


def _dataset(unzipped=None, zipped=None):
    dataset = MagicMock()
    dataset.id = "dataset-uuid"
    dataset.stable_id = "mdb-1-202401010000"
    dataset.unzipped_size_bytes = unzipped
    dataset.zipped_size_bytes = zipped
    return dataset


def _session(largest=None):
    session = MagicMock()
    session.query.return_value.filter.return_value.scalar.return_value = largest
    return session


class TestMeasureDataset(unittest.TestCase):
    """The size columns are nullable with no backfill, so every rung gets used."""

    def test_the_largest_file_wins(self):
        self.assertEqual(
            measure_dataset(_session(largest=500), _dataset(unzipped=9999)),
            (500, "largest file"),
        )

    def test_it_falls_back_to_the_unzipped_total(self):
        """A sum, so it overestimates - which routes up, not down."""
        self.assertEqual(
            measure_dataset(_session(), _dataset(unzipped=800)), (800, "unzipped total")
        )

    def test_it_falls_back_to_an_estimate_from_the_archive(self):
        measure, basis = measure_dataset(_session(), _dataset(zipped=100))

        self.assertEqual(measure, 500)
        self.assertEqual(basis, "estimated from the archive")

    def test_the_ratio_is_caller_supplied(self):
        measure, _ = measure_dataset(_session(), _dataset(zipped=100), 9)

        self.assertEqual(measure, 900)

    def test_nothing_recorded(self):
        self.assertEqual(measure_dataset(_session(), _dataset()), (None, "unknown"))

    def test_a_failed_query_is_not_fatal(self):
        session = MagicMock()
        session.query.side_effect = RuntimeError("database gone")

        self.assertEqual(measure_dataset(session, _dataset()), (None, "unknown"))


class TestSizeForDataset(unittest.TestCase):
    def _call(self, session, dataset, override=None):
        feed = MagicMock()
        feed.id = "feed-uuid"
        feed.stable_id = "mdb-1"
        with patch(CONFIG_VALUE, return_value=override):
            return size_for_dataset(
                session, feed, dataset, tiers=TIERS, namespace="demo"
            ).size

    def test_it_routes_on_the_measurement(self):
        self.assertEqual(self._call(_session(largest=1), _dataset()), Size.S)
        self.assertEqual(self._call(_session(largest=3 * GB), _dataset()), Size.L)

    def test_an_unmeasurable_dataset_goes_to_the_largest(self):
        self.assertEqual(self._call(_session(), _dataset()), LARGEST)

    def test_a_pin_decides_outright(self):
        self.assertEqual(
            self._call(_session(largest=3 * GB), _dataset(), override="s"), Size.S
        )

    def test_a_pin_skips_the_measurement(self):
        """No point costing a query for an answer that cannot change the outcome."""
        session = MagicMock()
        session.query.side_effect = AssertionError("the dataset was measured")

        self.assertEqual(self._call(session, _dataset(), override="m"), Size.M)

    def test_an_unreadable_pin_falls_back_to_the_measurement(self):
        feed = MagicMock()
        with patch(CONFIG_VALUE, side_effect=RuntimeError("no config")):
            size = size_for_dataset(
                _session(largest=1), feed, _dataset(), tiers=TIERS, namespace="demo"
            ).size

        self.assertEqual(size, Size.S)

    def test_the_namespace_and_key_are_the_callers(self):
        feed = MagicMock()
        with patch(CONFIG_VALUE, return_value=None) as config:
            size_for_dataset(
                _session(largest=1),
                feed,
                _dataset(),
                tiers=TIERS,
                namespace="pmtiles_builder",
                key="worker",
            )

        self.assertEqual(
            config.call_args_list[0].args[:2], ("pmtiles_builder", "worker")
        )


class TestClassifyFailure(unittest.TestCase):
    """Read the exception, never a stored message."""

    def test_a_bare_memory_error(self):
        """The case that cannot be classified from text: its message is empty."""
        error = MemoryError()

        self.assertEqual(str(error), "")
        self.assertEqual(classify_failure(error), FailureKind.RESOURCE_MEMORY)

    def test_duckdb_out_of_memory(self):
        class OutOfMemoryException(Exception):
            pass

        error = OutOfMemoryException("Out of Memory Error: failed to allocate 256 KiB")

        self.assertEqual(classify_failure(error), FailureKind.RESOURCE_MEMORY)

    def test_enospc(self):
        error = OSError(28, "No space left on device", "/tmp/in-memory/stop_times.txt")

        self.assertEqual(classify_failure(error), FailureKind.RESOURCE_DISK)

    def test_duckdb_spill_filling_the_volume(self):
        """DuckDB reports a full spill directory as its own error, not an OSError."""

        class IOException(Exception):
            pass

        error = IOException("IO Error: Failed to write: No space left on device")

        self.assertEqual(classify_failure(error), FailureKind.RESOURCE_DISK)

    def test_anything_else(self):
        for error in (ValueError("no tables"), FileNotFoundError("archive missing")):
            with self.subTest(error=error):
                self.assertEqual(classify_failure(error), FailureKind.OTHER)

    def test_only_resource_kinds_are_resource(self):
        self.assertTrue(FailureKind.RESOURCE_MEMORY.is_resource)
        self.assertTrue(FailureKind.RESOURCE_DISK.is_resource)
        self.assertFalse(FailureKind.OTHER.is_resource)


class TestEscalate(unittest.TestCase):
    """Every None is a stop, because the alternative is a queue loop."""

    def test_it_moves_one_rung_up(self):
        self.assertEqual(escalate(Size.S, TIERS, attempts=1, max_attempts=3), Size.M)
        self.assertEqual(escalate(Size.M, TIERS, attempts=1, max_attempts=3), Size.L)

    def test_the_largest_rung_is_terminal(self):
        self.assertIsNone(escalate(Size.L, TIERS, attempts=1, max_attempts=3))

    def test_the_attempt_cap_is_terminal(self):
        self.assertIsNone(escalate(Size.S, TIERS, attempts=3, max_attempts=3))
        self.assertIsNone(escalate(Size.S, TIERS, attempts=9, max_attempts=3))

    def test_an_unknown_current_rung_is_terminal(self):
        """Better to stop than to guess which worker just died."""
        self.assertIsNone(escalate(None, TIERS, attempts=0, max_attempts=3))


class TestConfiguredSize(unittest.TestCase):
    """An override decides; otherwise the measurement does. Nothing else."""

    def _route(self, largest, value=None):
        feed = MagicMock()
        with patch(CONFIG_VALUE, return_value=value):
            return size_for_dataset(
                _session(largest=largest),
                feed,
                _dataset(),
                tiers=TIERS,
                namespace="demo",
            )

    @staticmethod
    def _auto(size):
        """What the builder writes for itself, as opposed to a person's bare value."""
        return {"size": size, "source": "auto"}

    def test_an_override_beats_a_larger_measurement(self):
        self.assertEqual(self._route(10 * GB, "s").size, Size.S)
        self.assertEqual(self._route(10 * GB, self._auto("s")).size, Size.S)

    def test_an_override_beats_a_smaller_measurement(self):
        self.assertEqual(self._route(1, "l").size, Size.L)
        self.assertEqual(self._route(1, self._auto("l")).size, Size.L)

    def test_the_source_is_recorded_but_does_not_change_the_outcome(self):
        """Both decide outright; `basis` says who, for the record."""
        by_person = self._route(10 * GB, "s")
        by_builder = self._route(10 * GB, self._auto("s"))

        self.assertEqual(by_person.size, by_builder.size)
        self.assertEqual(by_person.basis, Basis.OPERATOR)
        self.assertEqual(by_builder.basis, Basis.AUTO)

    def test_an_unusable_value_falls_back_to_the_measurement(self):
        for value in ("xl", {"size": "xl", "source": "auto"}, {}, 3):
            with self.subTest(value=value):
                routing = self._route(1, value)

                self.assertEqual(routing.size, Size.S)
                self.assertEqual(routing.basis, Basis.MEASURED)

    def test_nothing_configured_reads_as_measured(self):
        routing = self._route(1)

        self.assertEqual(routing.size, Size.S)
        self.assertEqual(routing.basis, Basis.MEASURED)

    def test_an_override_skips_the_measurement_entirely(self):
        feed = MagicMock()
        session = MagicMock()
        session.query.side_effect = AssertionError("the dataset was measured")

        with patch(CONFIG_VALUE, return_value="m"):
            routing = size_for_dataset(
                session, feed, _dataset(), tiers=TIERS, namespace="demo"
            )

        self.assertEqual(routing.size, Size.M)


if __name__ == "__main__":
    unittest.main()
