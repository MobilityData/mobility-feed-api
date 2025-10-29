import os
import tempfile
import unittest
from unittest.mock import MagicMock

from trips_processor import TripsProcessor
from csv_cache import CsvCache, TRIPS_FILE


class TestTripsProcessor(unittest.TestCase):
    def test_filename_constant(self):
        processor = TripsProcessor(csv_cache=MagicMock(), logger=MagicMock())
        self.assertEqual(processor.filename, TRIPS_FILE)

    def test_process_parses_rows(self):
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            trips_path = os.path.join(td, TRIPS_FILE)
            with open(trips_path, "w", encoding="utf-8") as f:
                f.write("route_id,service_id,trip_id,shape_id\n")
                f.write("r1,svc,t1,s1\n")
                f.write("r1,svc,t2,\n")

            processor = TripsProcessor(csv_cache, logger=MagicMock())
            # this should read the trips.txt from csv_cache.get_path and populate maps
            processor.process()

            # trip_to_route should contain both trips
            self.assertEqual(processor.trip_to_route.get("t1"), "r1")
            self.assertEqual(processor.trip_to_route.get("t2"), "r1")

            # route_to_shape should map r1 -> s1 -> [t1]
            self.assertIn("r1", processor.route_to_shape)
            self.assertIn("s1", processor.route_to_shape["r1"])
            self.assertEqual(processor.route_to_shape["r1"]["s1"]["trip_ids"], ["t1"])

            # trips_no_shapes_per_route should contain t2 for r1
            self.assertIn("r1", processor.trips_no_shapes_per_route)
            self.assertEqual(processor.trips_no_shapes_per_route["r1"], ["t2"])

    def test_process_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            trips_path = os.path.join(td, TRIPS_FILE)
            # create an empty file
            with open(trips_path, "w", encoding="utf-8"):
                pass

            processor = TripsProcessor(csv_cache, logger=MagicMock())
            # should not raise
            processor.process()

            self.assertEqual(processor.trip_to_route, {})
            self.assertEqual(processor.route_to_shape, {})
            self.assertEqual(processor.trips_no_shapes_per_route, {})


if __name__ == "__main__":
    unittest.main()
