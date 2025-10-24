import os
import tempfile
import unittest
from unittest.mock import MagicMock

from csv_cache import CsvCache


class TestCsvCache(unittest.TestCase):
    def test_get_path_and_set_workdir(self):
        with tempfile.TemporaryDirectory() as td:
            cache = CsvCache(workdir=td, logger=MagicMock())
            p = cache.get_path("foo.txt")
            self.assertTrue(p.startswith(td))
            self.assertTrue(p.endswith(os.path.join(td, "foo.txt")))

            # change workdir
            newdir = os.path.join(td, "sub")
            os.makedirs(newdir, exist_ok=True)
            cache.set_workdir(newdir)
            self.assertEqual(cache.get_path("bar.csv"), os.path.join(newdir, "bar.csv"))

    def test_get_index_and_safe_value_helpers(self):
        cache = CsvCache(workdir=tempfile.gettempdir(), logger=MagicMock())
        columns = ["one", "two", "three"]
        self.assertEqual(cache.get_index(columns, "two"), 1)
        self.assertIsNone(cache.get_index(columns, "missing"))

        # safe value from index: row as list
        row = ["val1", "", "  val3  "]
        self.assertEqual(cache.get_safe_value_from_index(row, 0), "val1")
        # empty cell returns default when provided
        self.assertEqual(cache.get_safe_value_from_index(row, 1, "def"), "def")
        # trimmed
        self.assertEqual(cache.get_safe_value_from_index(row, 2, ""), "val3")

        # out of range index returns default
        self.assertEqual(cache.get_safe_value_from_index(row, 10, "d"), "d")

        # floats and ints
        row2 = ["3.14", "notnum", "42"]
        self.assertAlmostEqual(cache.get_safe_float_from_index(row2, 0), 3.14)
        self.assertIsNone(cache.get_safe_float_from_index(row2, 1))
        self.assertEqual(cache.get_safe_int_from_index(row2, 2), 42)
        self.assertIsNone(cache.get_safe_int_from_index(row2, 0))


if __name__ == "__main__":
    unittest.main()
