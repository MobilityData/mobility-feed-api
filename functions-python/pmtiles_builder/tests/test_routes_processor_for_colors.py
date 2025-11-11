import os
import tempfile
import unittest
from unittest.mock import MagicMock

from routes_processor_for_colors import RoutesProcessorForColors
from csv_cache import CsvCache, ROUTES_FILE


class TestRoutesProcessorForColors(unittest.TestCase):
    def test_process_populates_map(self):
        with tempfile.TemporaryDirectory() as td:
            # prepare routes.txt with several entries, including an empty color
            routes_path = os.path.join(td, ROUTES_FILE)
            with open(routes_path, "w", encoding="utf-8") as f:
                f.write("route_id,route_color\n")
                f.write("r1,FF0000\n")
                # insert an empty line which should be ignored by the processor
                f.write("\n")
                f.write("r2,\n")
                f.write("r3,00FF00\n")

            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            processor = RoutesProcessorForColors(csv_cache, logger=MagicMock())

            # run processing
            processor.process()

            # assert map contains expected values
            self.assertIn("r1", processor.route_colors_map)
            self.assertIn("r2", processor.route_colors_map)
            self.assertIn("r3", processor.route_colors_map)
            self.assertEqual(processor.route_colors_map["r1"], "FF0000")
            # empty color should be treated as missing -> "" (transform.get_safe_value returns default)
            self.assertEqual(processor.route_colors_map["r2"], "")
            self.assertEqual(processor.route_colors_map["r3"], "00FF00")

    def test_missing_color_column(self):
        with tempfile.TemporaryDirectory() as td:
            # prepare routes.txt with route_id only
            routes_path = os.path.join(td, ROUTES_FILE)
            with open(routes_path, "w", encoding="utf-8") as f:
                f.write("route_id\n")
                f.write("r1\n")

            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            processor = RoutesProcessorForColors(csv_cache, logger=MagicMock())

            processor.process()
            # route present but color column missing -> value should be ""
            self.assertIn("r1", processor.route_colors_map)
            self.assertEqual(processor.route_colors_map["r1"], "")

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            # create an empty routes.txt
            routes_path = os.path.join(td, ROUTES_FILE)
            open(routes_path, "w", encoding="utf-8").close()

            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            processor = RoutesProcessorForColors(csv_cache, logger=MagicMock())

            processor.process()
            # no rows processed -> map remains empty
            self.assertEqual(processor.route_colors_map, {})

    def test_missing_route_id_column(self):
        with tempfile.TemporaryDirectory() as td:
            routes_path = os.path.join(td, ROUTES_FILE)
            with open(routes_path, "w", encoding="utf-8") as f:
                # header lacks route_id
                f.write("route_color\n")
                f.write("FF0000\n")

            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            processor = RoutesProcessorForColors(csv_cache, logger=MagicMock())

            processor.process()
            # no route_id column -> no entries should be recorded
            self.assertEqual(processor.route_colors_map, {})


if __name__ == "__main__":
    unittest.main()
