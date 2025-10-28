import tempfile
import unittest
from unittest.mock import MagicMock

from csv_cache import CsvCache
from agencies_processor import AgenciesProcessor


class TestAgenciesProcessor(unittest.TestCase):
    def test_process_populates_agencies(self):
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            agencies_path = csv_cache.get_path("agency.txt")
            with open(agencies_path, "w", encoding="utf-8") as f:
                f.write("agency_id,agency_name\n")
                f.write("a1,Agency One\n")
                f.write("a2,Agency Two\n")

            proc = AgenciesProcessor(csv_cache, logger=MagicMock())
            proc.process()

            self.assertIn("a1", proc.agencies)
            self.assertIn("a2", proc.agencies)
            self.assertEqual(proc.agencies["a1"], "Agency One")
            self.assertEqual(proc.agencies["a2"], "Agency Two")

    def test_ignores_blank_and_empty_agency_id_and_trims_name(self):
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            agencies_path = csv_cache.get_path("agency.txt")
            with open(agencies_path, "w", encoding="utf-8") as f:
                f.write("agency_id,agency_name\n")
                f.write("\n")
                f.write(",No ID Agency\n")
                f.write("a3,  Trimmed Agency  \n")

            proc = AgenciesProcessor(csv_cache, logger=MagicMock())
            proc.process()

            # blank and missing agency_id rows are ignored; a3 present and name trimmed
            self.assertNotIn("", proc.agencies)
            self.assertIn("a3", proc.agencies)
            self.assertEqual(proc.agencies["a3"], "Trimmed Agency")

    def test_empty_file_results_in_empty_agencies(self):
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            agencies_path = csv_cache.get_path("agency.txt")
            # create empty file
            with open(agencies_path, "w", encoding="utf-8"):
                pass

            proc = AgenciesProcessor(csv_cache, logger=MagicMock())
            proc.process()

            self.assertEqual(proc.agencies, {})

    def test_missing_file_is_handled_gracefully(self):
        # If agency.txt does not exist, processor should not raise and agencies remain empty
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            # Do not create agency.txt

            proc = AgenciesProcessor(csv_cache, logger=MagicMock())
            # Should not raise
            proc.process()

            self.assertEqual(proc.agencies, {})


if __name__ == "__main__":
    unittest.main()
