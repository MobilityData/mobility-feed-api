import os
import tempfile
import unittest
from unittest.mock import MagicMock

from csv_cache import CsvCache
from stop_times_processor import StopTimesProcessor


class DummyTripsProcessor:
    def __init__(self, trips_no_shapes_per_route, trip_to_route):
        # expected shape: route_id -> list of trip_ids
        self.trips_no_shapes_per_route = trips_no_shapes_per_route
        # trip_id -> route_id mapping
        self.trip_to_route = trip_to_route

    def clear_trip_to_route(self):
        self.trip_to_route = {}


class TestStopTimesProcessor(unittest.TestCase):
    def test_collects_trips_and_aliases_and_stop_to_routes(self):
        with tempfile.TemporaryDirectory() as td:
            # Prepare stop_times.txt
            stops_path = os.path.join(td, "stop_times.txt")
            with open(stops_path, "w", encoding="utf-8") as f:
                # only trip_id and stop_id (processor ignores times)
                f.write("trip_id,stop_id,stop_sequence\n")
                f.write("t1,stop1,1\n")
                f.write("t1,stop2,2\n")
                f.write("t2,stop1,1\n")
                f.write("t2,stop2,2\n")
                f.write("t3,stop3,1\n")

            csv_cache = CsvCache(workdir=td, logger=MagicMock())

            # trips without shapes (all three listed). Sorted order: ['t1','t2','t3']
            trips_no_shapes_per_route = {"r1": ["t1", "t2", "t3"]}
            trip_to_route = {"t1": "r1", "t2": "r2", "t3": "r1"}
            dummy = DummyTripsProcessor(trips_no_shapes_per_route, trip_to_route)

            processor = StopTimesProcessor(
                csv_cache, logger=MagicMock(), trips_processor=dummy
            )

            # run processing
            processor.process()

            # canonical should contain t1 and t3 (t2 is same as t1)
            self.assertIn("t1", processor.trip_with_no_shape_to_stops)
            self.assertIn("t3", processor.trip_with_no_shape_to_stops)
            self.assertNotIn("t2", processor.trip_with_no_shape_to_stops)

            self.assertEqual(
                processor.trip_with_no_shape_to_stops["t1"], ["stop1", "stop2"]
            )
            self.assertEqual(processor.trip_with_no_shape_to_stops["t3"], ["stop3"])

            # aliases: t2 -> t1
            self.assertIn("t2", processor.trip_with_no_shape_same_as)
            self.assertEqual(processor.trip_with_no_shape_same_as["t2"], "t1")

            # stop_to_routes mapping: stop1 -> {r1, r2}, stop2 -> {r1, r2}, stop3 -> {r1}
            self.assertEqual(processor.stop_to_routes["stop1"], {"r1", "r2"})
            self.assertEqual(processor.stop_to_routes["stop2"], {"r1", "r2"})
            self.assertEqual(processor.stop_to_routes["stop3"], {"r1"})

            # helper methods
            self.assertEqual(processor.get_trip_alias("t2"), "t1")
            self.assertEqual(processor.get_stops_from_trip("t1"), ["stop1", "stop2"])

    def test_ignores_blank_lines_and_missing_fields(self):
        with tempfile.TemporaryDirectory() as td:
            stops_path = os.path.join(td, "stop_times.txt")
            with open(stops_path, "w", encoding="utf-8") as f:
                f.write("trip_id,stop_id,stop_sequence\n")
                f.write("\n")
                f.write("t1,stop1,1\n")
                f.write(",,\n")  # malformed/empty row should be skipped

            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            trips_no_shapes_per_route = {"r1": ["t1"]}
            trip_to_route = {"t1": "r1"}
            dummy = DummyTripsProcessor(trips_no_shapes_per_route, trip_to_route)
            processor = StopTimesProcessor(
                csv_cache, logger=MagicMock(), trips_processor=dummy
            )

            processor.process()

            # still processes t1
            self.assertIn("t1", processor.trip_with_no_shape_to_stops)
            self.assertEqual(processor.trip_with_no_shape_to_stops["t1"], ["stop1"])

    def test_inverted_stop_sequence_is_normalized_and_aliased(self):
        """A trip with stops in inverted sequence should be normalized and deduplicated against an identical trip."""
        with tempfile.TemporaryDirectory() as td:
            stops_path = os.path.join(td, "stop_times.txt")
            with open(stops_path, "w", encoding="utf-8") as f:
                f.write("trip_id,stop_id,stop_sequence\n")
                # t1 has inverted order (2 before 1)
                f.write("t1,stop2,2\n")
                f.write("t1,stop1,1\n")
                # t2 has correct order
                f.write("t2,stop1,1\n")
                f.write("t2,stop2,2\n")

            csv_cache = CsvCache(workdir=td, logger=MagicMock())

            trips_no_shapes_per_route = {"r1": ["t1", "t2"]}
            trip_to_route = {"t1": "r1", "t2": "r1"}
            dummy = DummyTripsProcessor(trips_no_shapes_per_route, trip_to_route)

            processor = StopTimesProcessor(
                csv_cache, logger=MagicMock(), trips_processor=dummy
            )
            processor.process()

            # After normalization both trips should map to the same canonical stops
            # canonical should contain only the first trip (sorted order 't1','t2' -> t1 canonical)
            self.assertIn("t1", processor.trip_with_no_shape_to_stops)
            self.assertNotIn("t2", processor.trip_with_no_shape_to_stops)
            self.assertEqual(
                processor.trip_with_no_shape_to_stops["t1"], ["stop1", "stop2"]
            )

            # alias recorded: t2 -> t1
            self.assertIn("t2", processor.trip_with_no_shape_same_as)
            self.assertEqual(processor.trip_with_no_shape_same_as["t2"], "t1")


if __name__ == "__main__":
    unittest.main()
